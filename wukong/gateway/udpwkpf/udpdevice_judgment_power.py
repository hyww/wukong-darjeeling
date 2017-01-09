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
        self.power_offTime =self.Power_Off(0)
        self.power_onTime = self.Power_On()
        print "Judgment Power init success"

    def Power_Off(self,onFlg):    
       self. power_offCnt = 0
       self. checkContinueZero = 0
       with open('drinkdata.csv','rt') as fin:
	   cin = csv.reader(fin)
	   test = [row for row in cin]

       for column in test[1:]:
          if int(column[2]) == 0 or int(column[2]) == 1:
            self.checkContinueZero = 1
            self.power_offCnt += 1
            if self.power_offCnt == 1:
	      self.power_offTime = column[1]
	  else:
	    if self.power_offCnt >= 8 and onFlg == 1:
	      return column[1]
	    self.checkContinueZero = 0
            self.power_offCnt = 0

	  if self.power_offCnt == 8 and self.checkContinueZero == 1 and onFlg == 0:
	    return int(self.power_offTime)

    def Power_On(self):
       self.power_onTime =self.Power_Off(1)
       print(self.power_onTime)  
 
    def update(self,obj,pID,val):
        print(self.intervalNum)
        self.intervalNum += 1
        self.intervalNum = self.intervalNum % 48
        if self.intervalNum == self.power_offTime:
          obj.setProperty(5,0)
        
        if self.intervalNum == self.power_onTime:
          obj.setProperty(5,1)
        

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
