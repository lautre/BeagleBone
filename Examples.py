# -*- coding: utf-8 -*-
"""
Created on Fri Jun 01 13:19:57 2012

@author: Laurent Trembloy
"""
from BeagleBone import *
from Peripherals import *

#Register class example

pwmclock=Register(0x44e00000,0xd4)#base address=CM_PER_BASE, offset =CM_PER_EPWMSS0_CLKCTRL
#by default, registers are 32bits
print pwmclock
 #value of the register :=> addr : 2000D4, value : 30000

#logical operators implemented
#pwmclock|=mask
#pwmclock&=mask
#pwmclock^=mask

#setting value
#pwmclock.value=value

#Pin examples
p=Pin('P8',3) # third pin on connector P8
print p.name
 #=>gpmc_ad6
print p.mux
 #=> hex value : 30, Mux mode : 0, pull enabled : 0, pullup : 1, input : 1
print p.signal
#=>[' gpmc_ad6 ', ' mmc1_dat6 ', ' NA ', ' NA ', ' NA ', ' NA ', ' NA ', ' gpio1_6']
p.mux.pull=1 # disable pullup/down
print p.mux.pull
#=> 1
print p.mux
#=> hex value : 38, Mux mode : 0, pull enabled : 1, pullup : 1, input : 1
print p.mux.mode
#=> 0

#Digital IO examples
#Generic IO
g=GPIO('P8',3)#Generic IO, constructor take care of initialization : retrieve sysfs filename,
#export the pin, handle all related files direction, value, edge
#all files are open and closed at each access
#if unable to export the pin, will unexport and export again (works as by now)
print g.direction
#=>
print g.edge
#=>
print g.value
#=>

o=Output('P8',3)# digital output, inherit from GPIO, constructor will try to retrieve configuration informations from
#the relevant files : mux mode, mux direction
o.on #set pin high
o.toggle()# inverse pin state
print o.value
#=>
o.trigger#inverse pin state, same as toggle, but as property
print o.value
o.trigger=1#inverse pin state, and revert it after 1sec, won't stop execution as it's a Timer
print o.value
sleep(1.1)
print o.value
o.train(1,[1,2,1,2,2,1],1)#will toggle pin repeatedly with successive durations, runs in separate Timers
#will have to wait train finished before using pin again????
sleep(10)
o.clock(2,5,0)#will generate a 0.5Hz symetric clock for 5 sec, wait 5 sec before using this pin again!!!!!!
sleep(5)



#test PCA9554 I2C port extender

p=PCA9554(2,0)#I2C2, A0=0,A1=0,A2=0
p.config=0b00000000#all pins set to output
p.output=0b00000000#setting all outputs low
p[0]=1#activate output 1, leaving other pins unchanged
print p[0] # print state of output 0
print p[0:5] #print state of outputs 0 to 4
p.demux=2# activate pin 2, setting all other pins to 0
print p.input # print state of input register different from real output state





