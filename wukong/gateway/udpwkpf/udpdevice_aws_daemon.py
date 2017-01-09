from twisted.web.client import FileBodyProducer
from twisted.protocols import basic
from twisted.internet import reactor
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient

from udpwkpf import WuClass, Device
import sys
import json

if __name__ == "__main__":
    class AWS_Daemon(WuClass):
        def __init__(self):
            WuClass.__init__(self)
            self.loadClass('AWS_Daemon')
            self.id = 0
            self.dataNo = 0;
            self.myMQTTClient = AWSIoTMQTTClient("")
            self.myMQTTClient.configureEndpoint("a13mxqj7o85rqq.iot.ap-northeast-1.amazonaws.com",8883)
            self.myMQTTClient.configureCredentials("AWS/root.crt", "AWS/private.key", "AWS/cert.crt")
            self.myMQTTClient.configureOfflinePublishQueueing(-1)  # Infinite offline Publish queueing
            self.myMQTTClient.configureDrainingFrequency(2)  # Draining: 2 Hz
            self.myMQTTClient.configureConnectDisconnectTimeout(10)  # 10 sec
            self.myMQTTClient.configureMQTTOperationTimeout(5)  # 5 sec
            self.myMQTTClient.connect()
            print "aws init success"

        def Callback(self, client, userdata, message, pID):
            print("Received a new message: ")
            print(message.payload)
            print("from topic: ")
            print(message.topic)
            print("--------------\n\n")
            try:
                data = json.loads(message.payload)
                if 'data' in data and sys.argv[1] != '-t':
                    self.obj.setProperty(pID, data['data'])
            except ValueError, e:
                print 'not JSON'

        def LCallback(self, client, userdata, message):
            self.Callback(client, userdata, message, 1)
        
        def RCallback(self, client, userdata, message):
            self.Callback(client, userdata, message, 2)

        def update(self,obj,pID=None,val=None):
            if self.id != (int)(obj.getProperty(0)) or self.dataNo != (int)(obj.getProperty(6)):
                self.id = (int)(obj.getProperty(0))
                self.dataNo = (int)(obj.getProperty(6))
                self.obj = obj
                print self.id, ",", self.dataNo
                self.myMQTTClient.subscribe('Device/'+str(self.id)+'/L/Recv/'+str(self.dataNo), 1, self.LCallback)
                self.myMQTTClient.subscribe('Device/'+str(self.id)+'/R/Recv/'+str(self.dataNo), 1, self.RCallback)

            if pID == 3:
                print pID
                msg = json.dumps({'data': val})
                self.myMQTTClient.publish('Device/'+str(self.id-1)+'/R/Recv/'+str(self.dataNo), msg, 0)
            if pID == 4:
                print pID
                msg = json.dumps({'data': val})
                self.myMQTTClient.publish('Device/'+str(self.id+1)+'/L/Recv/'+str(self.dataNo), msg, 0)

    class MyDevice(Device):
        def __init__(self,addr,localaddr):
            Device.__init__(self,addr,localaddr)

        def init(self):
            self.m = AWS_Daemon()
            self.addClass(self.m,0)
            self.obj_philip = self.addObject(self.m.ID)
    if sys.argv[1] == '-t':
        a = AWS_Daemon()
        a.id = (int)(sys.argv[2])
        a.dataNo = (int)(sys.argv[3])
	a.myMQTTClient.subscribe('Device/'+str(a.id)+'/L/Recv/'+str(a.dataNo), 1, a.LCallback)
	a.myMQTTClient.subscribe('Device/'+str(a.id)+'/R/Recv/'+str(a.dataNo), 1, a.RCallback)
	reactor.run()
     
    elif len(sys.argv) <= 2:
        print 'python %s <gip> <dip>:<port>' % sys.argv[0]
        print '      <gip>: IP addrees of gateway'
        print '      <dip>: IP address of Python device'
        print '      <port>: An unique port number'
        print ' ex. python %s 192.168.4.7 127.0.0.1:3000' % sys.argv[0]
        sys.exit(-1)

    else:   
	d = MyDevice(sys.argv[1],sys.argv[2])
	reactor.run()
