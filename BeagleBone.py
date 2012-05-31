#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Created on Wed May 23 10:42:17 2012

@author: Laurent Trembloy

Beware : if a particular function is not availlable for a particular pin, the program will exit with error
Not sure that's a bad idea
All informations have been gathered on different blogs, forums and so on
Works for me with Angstrom, kernel 3.2.18
Tried to be as Pythonic as possible
Everything is an object
Tried to code like I speek, and hide complexity
"""

import sys
import select

from time import *
from struct import *
from math import *

from threading import Timer
from mmap import mmap
from fcntl import ioctl

class Register(object):
    '''Memory Map acces to the register of the BeagleBone Processor'''
    mmapoffset=0x44c00000             #MMAP_OFFSET
    mmapsize=  0x48ffffff-mmapoffset  #MMAP_SIZE
    formats={32:'<L',16:'<H'}         #32 or 16 bits

    def __init__(self,baseaddr,offset,size=32):
        self.addr=baseaddr+offset-self.mmapoffset
        self.format=self.formats[size]
        self.length=size/8
        print self.value
        return

    def __repr__(self):
        return 'addr : %X, value : %X'%(self.addr,self.value)

    def __ior__(self,mask):
        self.value=self.value|mask
        return self.value

    def __iand__(self,mask):
        self.value=self.value&mask
        return self.value

    def __ixor__(self,mask):
        self.value=self.value^mask
        return self.value

    @property
    def value(self):
        with open('/dev/mem','r+b') as f:
            f.flush()
            mem=mmap(f.fileno(),self.mmapsize,offset=self.mmapoffset)
            return unpack(self.format, mem[self.addr:self.addr+self.length])[0]
    @value.setter
    def value(self,val):
        with open('/dev/mem','r+b') as f:
            mem=mmap(f.fileno(),self.mmapsize,offset=self.mmapoffset)
            mem[self.addr:self.addr+self.length]= pack(self.format, val)
        return

class MuxMode(object):
    ''' class taking care of correct mux mode handling,
        mode, pullups, direction and value are handled by properties'''
    _value=0
    _pull=0
    _up=0
    _mode=0
    _input=0

    def __init__(self,pin):
        '''Instantiated by a Pin object, or valid pin name'''
        if isinstance(pin,Pin):
            self.name=pin.name
        else:
            self.name=pin
        return

    def __repr__(self):
        return ' hex value : %X, Mux mode : %d, pull enabled : %d, pullup : %d, input : %d'%(self.value,self.mode,self.pull,self.up,self.input)

    @property
    def set(self):
        '''set Mux mode and other values'''
        fw=file('/sys/kernel/debug/omap_mux/'+self.name,'w')
        fw.write('%X'%self._value)
        fw.close()
        return self._value

    @property
    def value(self):
        '''retriev values from muxmode'''
        fw=file('/sys/kernel/debug/omap_mux/'+self.name,'r')
        result=fw.read().strip()
        fw.close()
        self._value=int(result.split('= 0x')[1][:4],16)
        return self._value
    @value.setter
    def value(self,value):

        self._mode=value&0b000111
        self._up=(value&0b010000)>>4
        self._pull=(value&0001000)>>3
        self._input=(value&0b100000)>>5
        self._value=value
        self.set
        return

    @property
    def mode(self):
        self._mode=self.value&(0b000111)
        return self._mode
    @mode.setter
    def mode(self,value):
        if value>7:
            print 'not allowed'
            return
        self._mode=value
        self._value&=~(0b000111)#clear bits
        self._value|=value#set bit
        self.set
        return

    @property
    def up(self):
        self._up=(self.value&0b010000)>>4
        return self._up
    @up.setter
    def up(self,value):
        if value>1:
            print 'not allowed'
            return
        self._up=value
        value=value<<4#set bit mask
        self._value&=~(0b010000)#clear bit
        self._value|=value#set bit
        self.set
        return

    @property
    def pull(self):
        self._pull=(self.value&0b001000)>>3
        return self._pull
    @pull.setter
    def pull(self,value):
        '''modify and set the pullup'''
        if value>1:
            print 'not allowed'
            return
        self._pull=value
        value=value<<3#set bit mask
        self._value&=~(0b001000)#clear bit
        self._value|=value#set bit
        self.set
        return

    @property
    def input(self):
        self._input=(self.value&0b100000)>>5
        return self._input
    @input.setter
    def input(self,value):
        '''modify and set the IO direction'''
        print self._value
        if value>1:
            print 'not allowed'
            return
        self._input=value
        value=value<<5#set bit mask
        self._value&=~(0b100000)#clear bit
        self._value|=value#set bit
        self.set
        return

class Signals(object):
    '''Class dealing with availlable signals on a PIN
        implemented :
            Signal.gpio will return the filename for the gpio mode
            Signal.pwm will return the filename for the ehrpwm
            Signal.gpmc'''

# TODO : Handle I2C, SPI and other mode

    class Signal(object):

        def __init__(self,name,mode,number=0):
            '''
            name : name to be used for filesystem access
            mode : mode number to configure the mux
            number : gpio number, pwm 0/1,
            '''
            self.name=name
            self.mode=mode
            self.number=number
            return

        def __repr__(self):
            return '%s,%d'%(self.name,self.mode)

    def __init__(self,pin):
        '''Instantiated by a Pin object, or valid pin name'''
        if isinstance(pin,Pin):
            self.name=pin.name
        else:
            self.name=pin
        self.read()
        return

    def __repr__(self):
        return str(self.signals)

    def read(self):
        '''read the relevant file and try to gather information on mux mode availlable for the pin
        for now : instanciate  gpio, pwm, gpmc as Signal'''
        fw=file('/sys/kernel/debug/omap_mux/'+self.name,'r')
        result=fw.read().strip()
        fw.close()
        self.signals=result.split('\n')[-1].split('signals:')[1].split('|')
        gpio=self.signals[-1][5:].split('_')
        number=(int(gpio[0])*32+int(gpio[1]))
        gpio='gpio%d'%number
        self.gpio=Signals.Signal(gpio,7,number)
        for i,name in enumerate(self.signals[:-1]):
            name=name[1:-1]
            if name[:6]=='ehrpwm':
                channel=name[-1]=='B'
                pwm='ehrpwm.%s:%d'%(name[-2],channel)
                self.pwm=Signals.Signal(pwm,i,int(name[-2]))
                continue
            if name!='NA':
                attr=(name.split('_')[0]).strip()
                setattr(self,attr,Signals.Signal(name,i))

class Pin(object):
    '''Abstraction for dealing with pins on connector based on their physical position
    most of the initializations are done by reading system files'''

    names={   'P8':{3: 'gpmc_ad6',                          4: 'gpmc_ad7',
                    5: 'gpmc_ad2',                          6: 'gpmc_ad3',
                    7: 'gpmc_advn_ale' ,                    8: 'gpmc_adoen_ren',
                    9: 'gpmc_be0n_cle',                    10: 'gpmc_wen',
                    11:'gpmc_ad13',                        12: 'gpmc_ad12',
                    13:'gpmc_ad9',                         14: 'gpmc_ad10',
                    },
               'P9':{1:'GND',
                    }}
# TODO : add all pins

    def __init__(self,connector,pin):
        '''connector : P8/P9
        pin : pin number on connector'''

        self.name=self.names[connector][pin]
        self.mux=MuxMode(self)
        self.signal=Signals(self)
        return

class Pwm(Pin):
    '''Pwm class implementation
        for now prefer frequency and duty cycle in %, as I don't know if the values in filesystem are
        all updates at the same time'''
    clockbase=0x44e00000     #CM_PER_BASE
    clocks=[0xd4,0xcc,0xd8]  #CM_PER_EPWMSSx_CLKCTRL

    def __init__(self,connector,pin,frequency,duty):
        super(Pwm,self).__init__(connector,pin)
        self.mux.mode=self.signal.pwm.mode #mode number retrieved by Signals class
        self.mux.input=0
        self.mux.pull=0
        self.mux.up=0
        print self.mux
        self.filename='/sys/class/pwm/%s'%self.signal.pwm.name #file name retrieved by class Signals
        print self.filename
        self.clock=Register(self.clockbase,self.clocks[self.signal.pwm.number]) #Register instance to enable the clock for the given pwm
        print self.clock
        self.clock.value=0x02 #enable clock in registers
        self.request #request pwm, not sure if usefull
        self.frequency=frequency
        self.duty=duty
        return

    def __iadd__(self,value):
        self.duty=self.duty+value
        return

    def __isub__(self,value):
        self.duty=self.duty-value
        return

    def __imul__(self,value):
        self.duty=self.duty*value
        return

    def __idiv__(self,value):
        self.duty=self.duty/value
        return

    @property
    def request(self):
        with file(self.filename+'/request','r') as f:
            result=f.read()
            print result
        return result

    @property
    def duty(self):
        '''retrieve duty cycle in %'''
        with file(self.filename+'/duty_percent','r') as f:
            result=f.read()
            print result
        return float(result)
    @duty.setter
    def duty(self,duty):
        '''set duty cycle in %'''
        with file(self.filename+'/duty_percent','w') as f:
            f.write('%d'%int(duty))
        return

    @property
    def frequency(self):
        with file(self.filename+'/period_freq','r') as f:
            result=f.read()
            print result
        return float(result)
    @frequency.setter
    def frequency(self,frequency):
        '''set frequency of the pwm'''
        previous=self.duty                  #memorize the duty cycle
        self.duty=0                         #set duty cycle to 0% to change the frequency seemlessly
        with file(self.filename+'/period_freq','w') as f:
            f.write('%d'%int(frequency))
        self.duty=previous
        return

    @property
    def period(self):
        with file(self.filename+'/period_ns','r') as f:
            result=f.read()
            print result
        return float(result)
    @period.setter
    def period(self,period):
        self.duty=0
        with file(self.filename+'/period_ns','w') as f:
            f.write('%.3f'%period)
        return

    @property
    def run(self):
        with file(self.filename+'/run','r') as f:
            result=f.read()
            print result
        return int(result)
    @run.setter
    def run(self,value):
        value=value==1
        if not self.run:
            with file(self.filename+'/run','w') as f:
                f.write('%d'%int(value))
        return

    @property
    def start(self):
        '''for convenience'''
        self.run=1
        return

    @property
    def stop(self):
        '''for convenience'''
        self.run=0
        return

    def modulate(self,modulator):
        '''modulator need to be an iterable with a time constrain, ie function of time()'''
        for i in modulator:
            self.duty=i
        return

class Modulator(object):
    '''Example class for trigonometric function'''
    def __init__(self,func,frequency,steps):
        '''func must be a function of time, with return 0<value<100'''
        self.func=func
        self.frequency=float(frequency)
        self.steps=float(steps)
        return

    def __iter__(self):
        start=time()
        while 1:
            duty=50*self.func(2*pi*self.frequency*(time()-start))+50
            sleep(1./self.frequency/self.steps)
            yield duty



class Gpio(Pin):
    '''Base class for input and output pins'''

    def __init__(self,port,pin):
        super(Gpio,self).__init__(port,pin)
        self.filename='/sys/class/gpio/%s'%self.signal.gpio.name
        self.number=self.signal.gpio.number
        self.export
        return

    def __enter__(self):
        return self

    def __exit__(self,exc_type, exc_value, traceback):
        self.unexport #for use with "WITH" statement and exit gracefully by unexporting the gpio
        return

    @property
    def unexport(self):
        fw=file('/sys/class/gpio/unexport','w')
        fw.write('%d'%self.number)
        fw.close()
        return

    @property
    def export(self):
        try:
            fw=file('/sys/class/gpio/export','w')
            fw.write('%d'%self.number)
            fw.close()
        except:
            self.unexport
            self.export
        return

    @property
    def value(self):
        fw=file(self.filename+'/value','r')
        result=fw.read()
        fw.close()
        return int(result)
    @value.setter
    def value(self,value):
        '''1/0'''
        fw=file(self.filename+'/value','w')
        result=fw.write('%d'%value)
        fw.close()
        return result

    @property
    def edge(self):
        fw=file(self.filename+'/edge','r')
        result=fw.read()
        fw.close()
        return int(result)
    @edge.setter
    def edge(self,value):
        '''rising, both, falling, none'''
        fw=file(self.filename+'/edge','w')
        result=fw.write(value)
        fw.close()
        return result

    @property
    def direction(self):
        fw=file(self.filename+'/direction','r')
        result=fw.read()
        fw.close()
        return result
    @direction.setter
    def direction(self,value):
        '''in/out'''
        fw=file(self.filename+'/direction','w')
        result=fw.write(value)
        fw.flush()
        fw.close()
        return result

class Output(Gpio):

    def __init__(self,port,pin):
        super(Output,self).__init__(port,pin)
        self.mux.mode=7
        self.mux.pull=0
        self.mux.up=0
        self.mux.input=0
        return

    @property
    def on(self):
        self.value=1
        return

    @property
    def off(self):
        self.value=0
        return

    def toggle(self):
        self.value=abs(self.value-1)
        return

    def trigger(self,duration=0.001):
        '''toggle pin, lauch timer for duration and toggle again, as it is a thread, won't block the execution'''
        self.toggle()
        Timer(duration,self.toggle).start()
        return

    def train(self,state,liste,repeat=1):
        '''state : initial state
            liste : liste of the duration of th states [1,2,3,4]=> 1sec up, 2sec down, 3sec up, 4sec down (beware state depend on initial conditions
            repeat :
            once defined, the pulse train will live on itself, as these are Timer (see threading module)
            beware : program must last longer than the whole duration of the train, otherwise, the pwm file will be closed on exit of the main program
            '''
        self.value=state
        duration=sum(liste)
        for i in range(repeat):
            delay=0
            for t in liste:
                delay+=t
                Timer(i*duration+delay,self.toggle).start()
        return duration*repeat

    def clock(self,period,duration):
        start=time()
        while (time()-start)<=duration:
            self.toggle()
            sleep(period)
        return

class Input(Gpio):

    def __init__(self,port,pin):
        super(Input,self).__init__(port,pin)
        #configuration of the mux mode is always 7, pullup and polarity may be changed anytime
        self.mux.mode=7
        self.mux.pull=0
        self.mux.up=0
        self.mux.input=1
        return

    def poll(self,timeout=10):
        '''poll implemented as an iterator to use with for loop
        beware : if timeout will return anyway, have to check the value
        don't know if it would be usefull to raise an error'''
        starttime=time()
        while (time()-starttime)<=timeout:
            val=self.value
            yield val
        return -1

    def rising(self,timeout=10):
        '''poll for rising condition'''
        starttime=time()
        while self.value !=0:
            if time()-starttime>timeout:
                return 0
        while self.value !=1:
            if time()-starttime>timeout:
                return 0
        return 1

    def falling(self,timeout=10):
        '''poll for falling condition'''
        starttime=time()
        while self.value !=1:
            if time()-starttime>timeout:
                return 0
        while self.value !=0:
            if time()-starttime>timeout:
                return 0
        return 1

class Demux(object):
    '''Parent class for logical demux pe 74hct237 with latch and enable'''
    _output=0

    def __init__(self,addr,enable,latch):
        '''
        addr=(Output...)LSB...MSB
        enable=Output
        latch=Output
        '''
        self._enable=enable
        self._latch=latch
        self.addr=addr
        self.output=0
        return

    @property
    def output(self):
        return self._output
    @output.setter
    def output(self,value):
        b=bin(value).split('b')[1:].split()
        for bit,val in zip(self.addr,b):
            bit.value=val
        self._output=value
        return

    @property
    def latch(self):
        self._latch.on
        self._latch.off
        self._latch.on
        return

    @property
    def enable(self):
        self._enable.on
        return
    @property
    def disable(self):
        self._enable.off
        return

class Sync(object):

    def __init__(self,input,output,edge=0,delay=0,pol=0):
        self.input=input
        self.output=output
        self.delay=delay
        self.edge=edge
        self.pol=pol
        return

class I2C(object):

# TODO : verify availability of pins and file system
#    IOCTL_I2C_SLAVE=0x0703

    def __init__(self,port=2,addr=0x20):
        ''' port : from I2C2-SCL
            addr : I2C addr of the component'''
        self.addr=addr
        self.filename='/dev/i2c-%d'%(port+1)
        return

    def write(self,*message):
        form='B'*len(message)
        message=pack(form,*message)
        with open(self.filename,'r+',1) as f:
            ioctl(f,0x0703,self.addr)
            f.write(message)
        return

    def read(self,length=1):
        with open(self.filename,'r+',1) as f:
            ioctl(f,0x0703,self.addr)
            result=f.read(length)
            form=length*'B'
            result=unpack(form,result)
            if len(result)==1:
                result=result[0]
        return result

class PCA9554(I2C):

    def __init__(self,port=2,pinaddr=0):
        super(PCA9554,self).__init__(port,pinaddr+0x20)
        return

    def __getitem__(self,index):
        inp=bin(self.input)
        print inp
        inp=[int(x) for x in inp[2:]]
        print inp
        if isinstance(index,slice):
           while len(inp)<8:
               inp.insert(0,0)
        inp.reverse()
        print inp
        return inp[index]

    def __setitem__(self,index,value):
        inp=self.input
# TODO: implement slice
        mask=~(1<<index)
        if value:
            value=1<<index
        inp&=mask
        value|=inp
        self.output=value
        return


    def __ior__(self,value):
        value=value|self.input
        self.output=value
        return self

    def __iand__(self,value):
        value=self.input&value
        self.output=value
        return self

    def __ixor__(self,value):
        value=self.input^value
        self.output=value
        return self

    @property
    def demux(self):
        return self.input
    @demux.setter
    def demux(self,pin):
        '''simulate demux :
            pin=0 => off,
            else one pin acivated at a time'''
        if not pin:
            self.output=0
            return
        pin=1<<pin
        self.output=pin
        return

    @property
    def input(self):
        self.write(0)
        result=self.read()
        return result

    @property
    def output(self):
        self.write(1)
        result=self.read()
        return result
    @output.setter
    def output(self,value):
        self.write(1,value)
        return

    @property
    def polarity(self):
        self.write(2)
        result=self.read()
        return result
    @polarity.setter
    def polarity(self,value):
        self.write(2,value)
        return

    @property
    def config(self):
        self.write(3)
        result=self.read()
        return result
    @config.setter
    def config(self,value):
        self.write(3,value)
        return

# TODO : tests for each class

if __name__=='__main__':
    pca=PCA9554()
    pca[0]=0
    x=raw_input('q to quit, else string to evaluate')
    while x!='q':
        exec(x)
        x=raw_input('q to quit, else string to evaluate : ')

#    pca.config=0b00000000
#    print bin(pca.output)
#    pca.output=0b11111111
#    print bin(pca.output)
#    for i in range(256):
#        pca.output=i
#        print pca.output
#        sleep(0.5)


#    m=Modulator(sin,50,256)
#    p=Pwm('P8',13,100000,90)
#    p.modulate(m)

#    with Output(1,6) as led, Output(1,7) as sync, Input(1,2) as triggin:
#
#        print led.direction
#        print led.value
#        led.on
#        starttime=time()
#        duration=sync.train(0,(5,5,5,5,5,5,5,5),1)
#        while (time()-starttime)<duration:
#            led.value= triggin.value
#            if not triggin.rising(0.02):
#                print 'error rising',time()-starttime
#            led.value= triggin.value
#            if not triggin.falling(0.02):
#                print 'error falling',time()-starttime
#        print triggin.value