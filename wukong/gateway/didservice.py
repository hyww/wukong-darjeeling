try:
    import netifaces
except:
    print "Please install the bitarray module from pypi"
    print "e.g. sudo pip install netifaces"
    exit(-1)

import gtwconfig as CONFIG
import mptn as MPTN
import ipaddress
import dbdict
import utils

import gevent
from gevent import socket
import struct
from datetime import datetime
import logging
logging.basicConfig(level=CONFIG.LOG_LEVEL)
logger = logging.getLogger( __name__ )

MAX_DID_LEN = MPTN.MULT_PROTO_LEN_DID
AUTONET_MAC_ADDR_LEN = 8

class DIDService(object):
    def __init__(self, transport_radio_addr, radio_addr_len):
        self._db = dbdict.DBDict("gtw.sqlite")
        self._did_nodes = dbdict.DBDict("gtw_alloc_did.sqlite")
        self._ok_nets = dbdict.DBDict("gtw_ok_nets.sqlite")

        if not self._is_db_init():
            self._db_init(transport_radio_addr, radio_addr_len)

        # Check whether master is connectable and its did/prefix is valid or not
        self._get_prefix_from_master()

        if self._db["GTWSELF_DID"] is None:
            logger.error("cannot initialize gateway because of no prefix")
            exit(-1)
        else:
            logger.info("find gateway DID %d(%s)." % (self._db["GTWSELF_DID"], str(ipaddress.ip_address(self._db["GTWSELF_DID"]))))

        logger.info("initialized")

    def _db_init(self, transport_radio_addr, radio_addr_len):
        self._db["MASTER_IP_ADDR"] = CONFIG.MASTER_IP
        self._db["MASTER_TCP_PORT"] = CONFIG.MASTER_TCP_PORT
        self._db["MASTER_DID"] = 0 # 0.0.0.0

        # set_self_did_if
        # Note that the max length is 4 bytes
        if radio_addr_len > MAX_DID_LEN:
            logger.error("the length of radio address (%d) is beyond the system's capability"%radio_addr_len)
            self._clear_db()
            exit(-1)

        if isinstance(transport_radio_addr, int) and transport_radio_addr >= 2 ** (radio_addr_len*8):
            logger.error("transport_radio_addr(%d) is not within the range of the network of address length %d"%(transport_radio_addr, radio_addr_len))
            self._clear_db()
            exit(-1)
        elif isinstance(transport_radio_addr, tuple):# IPv4
            # if isinstance(transport_radio_addr, tuple) and len(transport_radio_addr) == 2:
            #     did_if = str(ipaddress.ip_interface("%s/%s"%(str(ipaddress.ip_address(transport_radio_addr[0])),str(transport_radio_addr[1]))))
            #     self._db["GTWSELF_DID_IF"] = did_if
            #     self._db["GTWSELF_DID_PORT"] = int(transport_radio_addr[3])
            # else:
            #     logger.error("For IPv4, Transport device address must be a tuple (IP, prefix length or netmask, port)")
            #     self._clear_db()
            #     exit(-1)
            self._clear_db()
            raise NotImplementedError

        self._db["GTWSELF_RADIO_ADDR"] = transport_radio_addr
        self._db["GTWSELF_RADIO_ADDR_LEN"] = radio_addr_len
        self._db["GTWSELF_NETWORK_SIZE"] = 2**(radio_addr_len*8)
        self._db["GTWSELF_DID"] = None
        self._db["GTWSELF_DID_PREFIX_LEN"] = (MAX_DID_LEN-radio_addr_len)*8
        self._db["GTWSELF_DID_NETMASK"] = int(("1"*(MAX_DID_LEN-radio_addr_len)*8)+("0"*radio_addr_len*8), 2)
        self._db["GTWSELF_DID_HOSTMASK"] = int(("0"*(MAX_DID_LEN-radio_addr_len)*8)+("1"*radio_addr_len*8), 2)
        self._db["GTWSELF_MAC_ADDR"] = self._get_mac_address()

        # set_self_ip_addr and tcp_port
        # Not test for IPv6
        if CONFIG.SELF_IP_INTERFACE not in netifaces.interfaces():
            logger.error("cannot find the IP network interface %s" % CONFIG.SELF_IP_INTERFACE)
            self._clear_db()
            exit(-1)

        try:
            ip_addr = netifaces.ifaddresses(CONFIG.SELF_IP_INTERFACE)[netifaces.AF_INET][0]['addr']
            self._db["GTWSELF_IP_ADDR"] = ip_addr
        except (IndexError, KeyError, ValueError):
            logger.error("cannot find any IP address from the IP network interface %s" % CONFIG.SELF_IP_INTERFACE)
            self._clear_db()
            exit(-1)
        self._db["GTWSELF_TCP_PORT"] = CONFIG.SELF_TCP_PORT

    def _get_mac_address(self):
        mac = [0xFF, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07]
        return mac

    def _is_db_init(self):
        if len(self._db) == 0:
            return False

        for i in ["GTWSELF_RADIO_ADDR","GTWSELF_RADIO_ADDR_LEN","GTWSELF_NETWORK_SIZE","GTWSELF_DID","GTWSELF_DID_PREFIX_LEN","GTWSELF_DID_NETMASK","GTWSELF_DID_HOSTMASK","GTWSELF_MAC_ADDR","GTWSELF_IP_ADDR","GTWSELF_TCP_PORT"]:
            if i not in self._db:
                return False

        return True

    def _clear_db(self):
        for key in self._db:
            del self._db[key]
        for key in self._did_nodes:
            del self._did_nodes[key]
        for key in self._ok_nets:
            del self._ok_nets[key]

    def _is_radio_address_set(self, radio_address):
        return radio_address in self._did_nodes

    def _set_radio_address(self, radio_address, value=True):
        assert isinstance(radio_address, int), "radio address(%s) must be integer instead of %s" % (str(radio_address), type(radio_address))
        assert radio_address < self._db["GTWSELF_NETWORK_SIZE"], "radio address(%d) cannot excede upper bound %d" % (radio_address, self._db["GTWSELF_NETWORK_SIZE"])
        self._did_nodes[radio_address] = value

    def _unset_radio_address(self, radio_address):
        if self._is_radio_address_set(radio_address):
            del self._did_nodes[radio_address]

    def _get_transport_radio_address(self, did):
        return did & self._db["GTWSELF_DID_HOSTMASK"]

    def _is_did_master(self, did):
        if did == self._db["MASTER_DID"]:
            return True
        return False

    def _is_did_self(self, did):
        if did == self._db["GTWSELF_DID"]:
            return True
        return False

    def _is_did_in_self_network(self, did):
        self_did = self._db["GTWSELF_DID"]
        if self_did is None:
            logger.error("gateway does not have a valid prefix of DID")
            return False

        did_obj = ipaddress.ip_address(did)
        self_did_network = ipaddress.ip_interface("%s/%d"%(str(ipaddress.ip_address(self_did)),self._db["GTWSELF_DID_PREFIX_LEN"])).network
        if did_obj in self_did_network:
            return self._is_radio_address_set(self._get_transport_radio_address(did))
        return False

    def _find_did_in_other_network(self, did):
        did_obj = ipaddress.ip_address(did)
        for ok_net in self._ok_nets:
            # ok_nets key = "DID/MASK" value = "IP:PORT"
            if did_obj in ipaddress.ip_interface(ok_net).network:
                return ok_net
            gevent.sleep(0)
        return None

    def _get_prefix_from_master(self):
        address = (self._db["MASTER_IP_ADDR"], self._db["MASTER_TCP_PORT"])

        dest_did = self._db["MASTER_DID"]
        self_did = self._db["GTWSELF_DID"]
        src_did = self_did if self_did is not None else 0xFFFFFFFF
        msg_type = MPTN.MULT_PROTO_MSG_TYPE_PFX
        msg_subtype = MPTN.MULT_PROTO_MSG_SUBTYPE_PFX_REQ
        header = utils.create_mult_proto_header_to_str(dest_did, src_did, msg_type, msg_subtype)
        payload = "RADDR=%d;LEN=%d;PORT=%d;MAC=%s" % (self._db["GTWSELF_RADIO_ADDR"], self._db["GTWSELF_RADIO_ADDR_LEN"], self._db["GTWSELF_TCP_PORT"], struct.pack("!BBBBBBBB",*self._db["GTWSELF_MAC_ADDR"]))
        success, message = self._send_to_and_recv_from(address, header+payload)

        if not success:
            logger.error("cannot get prefix assignment from master due to network problem")
            return None

        if len(message) > MPTN.MULT_PROTO_MSG_PAYLOAD_BYTE_OFFSET:
            logger.error("packet PFX ACK/NAK from master might not have the payload")
            return None

        dest_did, src_did, msg_type, msg_subtype = utils.extract_mult_proto_header_from_str(message)

        log_msg = utils.split_packet_header(message)
        log_msg = utils.formatted_print(log_msg)
        logger.debug("expect PFX ACK message, receives:\n" + log_msg)

        if msg_type != MPTN.MULT_PROTO_MSG_TYPE_PFX:
            logger.error("get incorrect msg type (%d) instead of PFX from master" % msg_type)
            return None

        if msg_subtype == MPTN.MULT_PROTO_MSG_SUBTYPE_PFX_NAK:
            logger.error("prefix request is refused by master")
            return None

        if msg_subtype != MPTN.MULT_PROTO_MSG_SUBTYPE_PFX_ACK:
            logger.error("get incorrect msg subtype (%d) instead of PFX  ACKfrom master" % msg_subtype)
            return None

        if dest_did != self_did:
            if self_did is None:
                self._db["GTWSELF_DID"] = dest_did
                logger.info("successfully process PFX ACK message and store the DID %d with prefix" % dest_did)
            else:
                logger.error("get a prefix %d different from originally assigned %s" % (dest_did, str(self_did)))
                exit(-1)
        else:
            logger.info("successfully check prefix with master")

    def _forward_to_final_ip_hop(self, address, message):
        assert isinstance(address, tuple) and len(address) == 2, "address should be a tuple"

        success, message = self._send_to_and_recv_from(address, message)

        if not success:
            logger.error("cannot forward packet to %s due to network problem" % str(address))
            return None

        if len(message) > MPTN.MULT_PROTO_MSG_PAYLOAD_BYTE_OFFSET:
            logger.error("packet FWD ACK/NAK from master might not have the payload")
            return None

        dest_did, src_did, msg_type, msg_subtype = utils.extract_mult_proto_header_from_str(message)

        log_msg = utils.split_packet_header(message)
        log_msg = utils.formatted_print(log_msg)
        logger.debug("expect FWD ACK message, receives:\n" + log_msg)

        if msg_type != MPTN.MULT_PROTO_MSG_TYPE_FWD:
            logger.error("get incorrect msg type (%d) instead of FWD from master" % msg_type)
            return None

        if msg_subtype == MPTN.MULT_PROTO_MSG_SUBTYPE_FWD_NAK:
            payload = message[MPTN.MULT_PROTO_MSG_PAYLOAD_BYTE_OFFSET:]
            logger.error("forwarding via %s fails with error %s" % (str(address), payload))
            return None

        if msg_subtype != MPTN.MULT_PROTO_MSG_SUBTYPE_FWD_ACK:
            logger.error("get incorrect msg subtype (%d) instead of FWD ACK from master" % msg_subtype)
            return None

        return None

    def _send_to_and_recv_from(self, address, message):
        sock = None
        for i in xrange(CONFIG.CONNECTION_RETRIES):
            try:
                sock = socket.create_connection(address, CONFIG.NETWORK_TIMEOUT)
                break
            except IOError as e:
                logger.error('failed to connect to master %s:%s: %s' % (address[0], address[1], str(e)))
        else:
            if sock is not None: sock.close()
            return (False, None)

        ret = (False, None)
        try:
            #sock.settimeout(CONFIG.NETWORK_TIMEOUT)
            utils.special_send(sock, message)

            message = utils.special_recv(sock)

            ret = (True, message)
        except socket.timeout:
            logger.error("socket is timeout with addr=%s with msg=%s" % (str(address), message))
        except socket.error as e:
            logger.error("gets socket error %s with addr=%s with msg=%s" % (str(e), str(address), message))
        except struct.error as e:
            logger.error("python struct cannot interpret message %s with error %s" % (message, str(e)))
        finally:
            sock.close()

        return ret

    '''
    Public functions
    '''

    def is_did_valid(self, did):
        # Check other known network
        # Then Check itself network
        # Last Check if it is master
        
        if self._is_did_master(did):
            return True

        if self._is_did_self(did):
            return True

        if self._is_did_in_self_network(did):
            return True

        if self._find_did_in_other_network(did) is not None:
            return True

        return False

    def handle_did_req_message(self, context, dest_did, src_did, msg_type, msg_subtype, payload):
        self_did = self._db["GTWSELF_DID"]
        if self_did is None:
            logger.error("gateway does not have a valid prefix of DID")
            return None
        radio_addr_len = self._db["GTWSELF_RADIO_ADDR_LEN"]

        if payload is None or len(payload) != AUTONET_MAC_ADDR_LEN:
            logger.error("the length of payload of DID REQ %d should be the same as that of Autonet Zigbee MAC address %d" % (len(payload), AUTONET_MAC_ADDR_LEN))
            return None            
        
        temp_radio_addr = context
        temp_did = (self_did & self._db["GTWSELF_DID_NETMASK"]) | temp_radio_addr
        if not self._is_radio_address_set(temp_radio_addr):
            address = (self._db["MASTER_IP_ADDR"], self._db["MASTER_TCP_PORT"])
            dest_did = self_did
            src_did = temp_did
            msg_type = MPTN.MULT_PROTO_MSG_TYPE_DID
            msg_subtype = MPTN.MULT_PROTO_MSG_SUBTYPE_DID_UPD
            header = utils.create_mult_proto_header_to_str(dest_did, src_did, msg_type, msg_subtype)

            success, message = self._send_to_and_recv_from(address, header+payload)

            if not success:
                logger.error("cannot get DID confirmation from master due to network problem")
                return None

            if len(message) > MPTN.MULT_PROTO_MSG_PAYLOAD_BYTE_OFFSET:
                logger.error("packet DID ACK/NAK from master might not have the payload")
                return None

            dest_did, src_did, msg_type, msg_subtype = utils.extract_mult_proto_header_from_str(message)
            payload = message[MPTN.MULT_PROTO_MSG_PAYLOAD_BYTE_OFFSET:]

            log_msg = utils.split_packet_header(message) + [payload]
            log_msg = utils.formatted_print(log_msg)
            logger.debug("expect DID ACK/NAK message, receives:\n" + log_msg)

            if msg_type != MPTN.MULT_PROTO_MSG_TYPE_DID:
                logger.error("get incorrect msg type (%d) instead of DID from master" % msg_type)
                return None

            if msg_subtype == MPTN.MULT_PROTO_MSG_SUBTYPE_DID_NAK:
                logger.error("DID registration is refused by master")
                return None

            if msg_subtype != MPTN.MULT_PROTO_MSG_SUBTYPE_DID_ACK:
                logger.error("get incorrect msg subtype (%d) instead of DID ACK from master" % msg_subtype)
                return None

            if temp_did != dest_did:
                logger.error("get an unknown DID %s different from originally assigned %s" % (payload, temp_payload))
                return None

            logger.debug("it is a valid DID ACK message")

            self._set_radio_address(temp_radio_addr)
            logger.info("successfully allocate DID on both gateway and master")

        dest_did = temp_did
        src_did = self._db["MASTER_DID"]
        msg_type = MPTN.MULT_PROTO_MSG_TYPE_DID
        msg_subtype = MPTN.MULT_PROTO_MSG_SUBTYPE_DID_OFFR
        header = utils.create_mult_proto_header_to_str(dest_did, src_did, msg_type, msg_subtype)
        return header

    def handle_fwd_message(self, context, dest_did, message):
        self_did = self._db["GTWSELF_DID"]
        if self_did is None:
            logger.error("gateway does not have a valid prefix of DID")
            return None

        # find the dest_did is in itselves network and return the radio address
        # or find the next ip and port of gateway to forward
        if self._is_did_master(dest_did):
            logger.debug("forward the message to master")
            self._forward_to_final_ip_hop((self._db["MASTER_IP_ADDR"],self._db["MASTER_TCP_PORT"]), message)
            return None

        if self._is_did_in_self_network(dest_did):
            logger.debug("forward the message to transport radio address directly")
            return self._get_transport_radio_address(dest_did)

        ok_net = self._find_did_in_other_network(dest_did)
        if ok_net is not None:
            # ok_nets key = "DID/MASK, value = "IP:PORT"
            # ok_net is the key
            address = self._ok_nets[ok_net].split(":")
            address[1] = int(address[1])
            address = tuple(address)
            logger.debug("forward the message to other known gateway")
            self._forward_to_final_ip_hop(address, message)
            return None

        logger.error("the dest_did %X is neither the master, within the gateway's network, nor within known others" % dest_did)
        return None

    def handle_pfx_upd_message(self, context, dest_did, src_did, msg_type, msg_subtype, payload):
        self_did = self._db["GTWSELF_DID"]
        if self_did is None:
            logger.error("gateway does not have a valid prefix of DID")
            return None

        if payload is None:
            logger.error("cannot update PFX table since payload is empty")
            return None
        
        for p in payload.split(";"):
            # payload "DID/MASK=IP:PORT"
            p = p.split("=")
            did_net = ipaddress.ip_interface(p[0]).network

            for ok_net in self._ok_nets:
                # ok_nets key = "DID/MASK" value = "IP:PORT"
                if did_net.overlaps(ipaddress.ip_interface(ok_net).network):
                    logger.error("cannot update PFX table because it %s overlaps with other existing network %s" % (p[0], ok_net))
                    return None

            # add corresponding network into ok_net
            self._ok_nets[p[0]] = p[1]
            logger.debug("the info of other network %s is updated successfully." % str(p))
        return None