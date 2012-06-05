# -*- coding: utf-8 -*-
"""
Created on Thu May 31 16:14:31 2012

@author: Laurent Trembloy
"""
from BeagleBone import *

class PCA9554(I2C):

    def __init__(self,port=2,pinaddr=0):
        super(PCA9554,self).__init__(port,pinaddr+0x20)
        return

    def __getitem__(self,index):
        inp=bin(self.input)
        inp=[int(x) for x in inp[2:]]
        if isinstance(index,slice):
           while len(inp)<8:
               inp.insert(0,0)
        inp.reverse()
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
    '''Synchronise an input event with an output event'''
    def __init__(self,input,output,edge=0,delay=0,pol=0):
        self.input=input
        self.output=output
        self.delay=delay
        self.edge=edge
        self.pol=pol
        return

# TODO : tests for each class

if __name__=='__main__':
    pca=PCA9554()
    pca[0]=0
    x=raw_input('q to quit, else string to evaluate')
    while x!='q':
        exec(x)
        x=raw_input('q to quit, else string to evaluate : ')
