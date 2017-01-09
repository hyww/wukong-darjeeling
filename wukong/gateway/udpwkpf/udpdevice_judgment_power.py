from twisted.internet import reactor
from udpwkpf import WuClass, Device
import sys
import csv
import datetime

class Judgment_Power(WuClass):
    def __init__(self):
        WuClass.__init__(self)
        self.loadClass('Judgment_Power')
        self.intervalNum = 0
        self.threshold = 40 # if avg below this, should shutdown in this interval
        self.conThres = 4 # how many consecutive shutdown interval we need to really shutdown
        with open('drinkdata.csv','r') as fin:
            cin = csv.reader(fin)
            csvdata =  [ row for row in cin][1:]
            data = [{'sum':0,'num':0} for i in range(48)]
            for i in range(len(csvdata)):
                if i == 0:
                    continue # skip column name
                data[int(csvdata[i][1])]['sum'] += int(csvdata[i][2])
                data[int(csvdata[i][1])]['num'] += 1
            self.avgData = list(map(lambda x:x['sum']/x['num'],data))
            self.conData = []
            last = False
            con = 1
            for i in range(48):
                if i == 0:
                    last = (self.avgData[i] >= self.threshold)
                elif last == (self.avgData[i] >= self.threshold):
                    con+= 1
                else:
                    #print last, con
                    if (not last) and con >= self.conThres:
                        self.conData+= [False for j in range(con)]
                    else:
                        self.conData+= [True for j in range(con)]
                    con = 1
                    last = (self.avgData[i] >= self.threshold)
            #print last, con
            if (not last) and con >= self.conThres:
                self.conData+= [False for j in range(con)]
            else:
                self.conData+= [True for j in range(con)]
            #print self.conData, len(self.conData)

        print "Judgment Power init success"

    def judge(self):
        #if self.avgData[self.intervalNum] >= self.threshold:
        if self.conData[self.intervalNum]:
            return True
        else:
            return False

    def update(self,obj,pID,val):
        self.intervalNum += 1
        self.intervalNum = self.intervalNum % 48
        obj.setProperty(4,self.judge())

if __name__ == "__main__":
    class MyDevice(Device):
        def __init__(self,addr,localaddr):
            Device.__init__(self,addr,localaddr)

        def init(self):
            cls = Judgment_Power()
            self.addClass(cls, self.FLAG_VIRTUAL)
            self.obj_fire_agent = self.addObject(cls.ID)

    if len(sys.argv) <= 2:
        print 'python %s <gip> <dip>:<port>' % sys.argv[0]
        print '      <gip>: IP addrees of gateway'
        print '      <dip>: IP address of Python device'
        print '      <port>: An unique port number'
        print ' ex. python %s 192.168.4.7 127.0.0.1:3000' % sys.argv[0]
        sys.exit(-1)

    d = MyDevice(sys.argv[1],sys.argv[2])
    reactor.run()
