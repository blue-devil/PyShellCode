#!/usr/bin/env python3
# Implements functions similar to
# https://github.com/IAIK/flush_flush/blob/master/sc/cacheutils.h

import struct

class opcodes(object):
    short_jump = b'\xeb'
    short_call = b'\xe8'
    mov_in_rax = b'\xb8'
    mov_in_rbx = b'\xbb'
    mov_in_rdx = b'\xba'
    pop_in_rcx = b'\x59'
    ret        = b'\xc3'
    syscall    = b'\xcd\x80'
    flush_rax  = b'\x0f\xae\x38'
    flush_addr = b'\x0f\xae\x3c\x25'
    nop        = b'\x90'
    mfence     = b'\x0f\xae\xf0'
    rdtsc      = b'\x0f\x31'
    rdtscp     = b'\x0f\x01\xf9'
    cpuid      = b'\x0f\xa2'

    @staticmethod
    def to_binary(data, c_type='i'):
        return struct.pack('=' + c_type, data)


def syscall_write(fd, buf, count=None):

    if not isinstance(buf, bytes):
        buf = bytes(buf, 'utf-8')

    if count is None:
        count = len(buf)

    return (
        opcodes.short_jump + opcodes.to_binary(19, 'b') # Jump to 2:
      + opcodes.mov_in_rax + opcodes.to_binary(4, 'i') # 1:
      + opcodes.mov_in_rbx + opcodes.to_binary(fd, 'i')
      + opcodes.mov_in_rdx + opcodes.to_binary(count, 'i')
      + opcodes.pop_in_rcx # Move return address from stack to rcx, contains payload
      + opcodes.syscall
      + opcodes.ret # Return to original caller (since return adress from our call was popped)
      + opcodes.short_call + opcodes.to_binary(-24, 'i') # 2: Call 1
      + buf
    )

def syscall_sched_yield():
    return (
        opcodes.mov_in_rax + opcodes.to_binary(0x9e, 'i')
      + opcodes.syscall
      + opcodes.ret # Return to original caller
    )

def call_rdtsc(nofence=False, begin=False, end=False):
    
    r = b''
    if begin:
        r += opcodes.cpuid
        r += opcodes.rdtscp
    elif end:
        r += opcodes.rdtscp
        r += opcodes.cpuid
    else:
        r += opcodes.rdtsc

    # rdtsc provides the time stamp in rdx and rax (each contains 32bit), we only return rax,
    # so we have to add the to registers together.
    # shl    $0x20,%rdx      
    # or     %rdx,%rax
    r += b'\x48\xc1\xe2\x20\x48\x09\xd0' 

    if not nofence:
        r = opcodes.mfence + r + opcodes.mfence
    # Return to original caller, rax contains now the full time stamp
    return r + opcodes.ret

def call_flush(ptr):
    return (b'\x48\xb8' + opcodes.to_binary(ptr, 'Q') + opcodes.flush_rax + opcodes.ret)

def call_maccess(ptr):
    return (b'\x48\xbb' + opcodes.to_binary(ptr, 'Q') + b'\x48\x8b\x03' + opcodes.ret)

def call_longnop(ptr):
    return opcodes.nop * 64


def call_onlyreload(ptr):
    r = b''
    r += opcodes.mfence
    r += opcodes.rdtsc 
    r += b'\x48\xc1\xe2\x20\x48\x09\xd0'
    r += opcodes.mfence
    # Save time measurement
    r += b'\x48\x89\xc1' # Mov rax in rcx

    # Memory access
    r += b'\x48\xbb'
    r += opcodes.to_binary(ptr, 'Q') 
    r += b'\x48\x8b\x03'
    
    r += opcodes.mfence
    r += opcodes.rdtsc 
    r += b'\x48\xc1\xe2\x20\x48\x09\xd0'
    r += opcodes.mfence
    r += b'\x48\x29\xc8' # Sub rcx from rax
    r += opcodes.ret
    return r

def call_flushandreload(ptr):
    r = b''
    r += opcodes.mfence
    r += opcodes.rdtsc 
    r += b'\x48\xc1\xe2\x20\x48\x09\xd0'
    r += opcodes.mfence
    # Save time measurement
    r += b'\x48\x89\xc1' # Mov rax in rcx

    # Memory access
    r += b'\x48\xbb'
    r += opcodes.to_binary(ptr, 'Q') 
    r += b'\x48\x8b\x03'
    
    r += opcodes.mfence
    r += opcodes.rdtsc 
    r += b'\x48\xc1\xe2\x20\x48\x09\xd0'
    r += opcodes.mfence
    r += b'\x48\x29\xc8' # Sub rcx from rax
    
    r += b'\x48\x89\xc1' # Mov rax in rcx
    r += b'\x48\xb8'
    r += opcodes.to_binary(ptr, 'Q')
    r += opcodes.flush_rax
    r += b'\x48\x89\xc8'
    r += opcodes.ret
    return r