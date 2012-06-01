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
# TODO : add all pins names

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

    def __repr__(self):
        return 'Pwm : %s, freq : %d, duty cycle : %d'%(self.name,self.frequency,self.duty)

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
        with file(self.filename+'/value','r') as fw:
            result=fw.read()
        return int(result)
    @value.setter
    def value(self,value):
        '''1/0'''
        with file(self.filename+'/value','w')as fw:
            result=fw.write('%d'%value)
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
        self.direction='out'
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

    @property
    def trigger(self):
        self.toggle()
    def trigger(self,duration=0.001):
        '''toggle pin, launch timer for duration and toggle again, as it is a thread, won't block the execution'''
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
        self.value=state#set initial state
        duration=sum(liste)#overall duration of the pulse train
        for i in range(repeat):
            delay=0
            for t in liste:
                delay+=t#delay before launching timer
                Timer(i*duration+delay,self.toggle).start()
        return duration*repeat

    def clock(self,period,duration,delay=0):#generate a clock of period and duration starting with delay
        def run():
            start=time()
            while (time()-start)<=duration:
                self.toggle()
                sleep(period)
            return
        Timer(delay,run).start()
        return

class Input(Gpio):

    def __init__(self,port,pin):
        super(Input,self).__init__(port,pin)
        #configuration of the mux mode is always 7, pullup and polarity may be changed anytime later
        self.mux.mode=7
        self.mux.pull=0
        self.mux.up=0
        self.mux.input=1
        self.direction='in'
        return

    def poll(self,timeout=10):
        '''poll implemented as an iterator to use with for loop
        beware : if timeout will return anyway, have to check the value
        don't know if it would be usefull to raise an error'''
        starttime=time()
        while (time()-starttime)<=timeout:
            val=self.value
            yield val
        return

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

class Sync(object):
    '''Synchronise an input event with an output event'''
    def __init__(self,input,output,edge=0,delay=0,pol=0):
        self.input=input
        self.output=output
        self.delay=delay
        self.edge=edge
        self.pol=pol
        return

class I2C(object):

# TODO : verify availability of pins and file system and configure them is needed
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

class Adc(object):
    '''maximum acquisition frequency is about 5KHz'''
    files={33:'ain4',35:'ain6',36:'ain5',37:'ain2',38:'ain3',39:'ain0',40:'ain1'}
    def __init__(self,connector='P9',pin=39):
        self.filename='/sys/devices/platform/omap/tsc/ain%d'%pin
        self.gain=1
        self.offset=0
        self.unit='V'
        self.rate=0
        self.timeout=10
        self._buff=[]
        self.timing=[]
        self.samples=1
        self._average=0
        self._rms=0
        self._ac=0
        self._cross=[]
        self._period=0
        return

    def __repr__(self):
        return '%d'%self.value

    def __iter__(self):
        while 1:
            yield self.value

    @property
    def value(self):
        with open(self.filename,'r') as f:
            result=f.read(4)
            result= ''.join([x for x in result if ord(x)!=0])
            result=int(result)
        return result

    @property
    def buffer(self):
        return self._buff
    @buffer.setter
    def buffer(self,samples):
        self.samples=samples
        self._buff=[]
        self._timing=[]
        t0=time()
        for i in range(samples):
            with open(self.filename,'r') as f:
                self.timing.append(time()-t0)
                result=f.read(4)
                result =''.join([x for x in result if ord(x)!=0])
                self._buff.append(int(result))
                if self.rate:
                    sleep(1./self.rate)
        self._average=0
        self._rms=0
        self._ac=0
        self._cross=[]
        return

    @property
    def average(self):
        if not self._average:
            self._average=sum(self.buffer)/self.samples
        return self._average

    @property
    def ac(self):
        if not self._ac:
            self._ac=[x-self.average for x in self.buffer]
        return self._ac

    @property
    def cross(self):
        if not self._cross:
            for i,j in enumerate(self.ac[:-1]):
                if j*self.ac[i+1]<=0:
                    self._cross.append(self.timing[i])
        return self._cross

    @property
    def period(self):
        if not self._period:
            temp=[]
            for i,j in enumerate(self.cross[:-1]):
                temp.append(abs(j-self.cross[i+1]))
            self._period=sum(temp)/len(temp)*2
        return self._period

    @property
    def frequency(self):
        return 1./self.period

    @property
    def rms(self):
        if not self._rms:
            self._rms=sqrt(sum([x*x for x in self.ac])/self.samples)
        return self._rms


if __name__=='__main__':

    a=Adc(pin=7)
    t0=time()
    a.buffer=2000
    print a.average
    print a.period
    print a.frequency
    print a.rms





