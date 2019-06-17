# if not '__profiling__' in globals():
#     raise Exception('Micropython Profiling feature is required!')

import sys

try:
    import micropython
except:
    pass

if not 'settrace' in dir(sys):
    print("SKIP")
    raise SystemExit

if 'micropython' in globals():
    print('this is micropython')
    from uio import open
else:
    print('this is other python')

def print_stacktrace(frame, level = 0):
    # back = frame.f_back

    if frame.f_globals['__name__'].startswith('importlib.'):
        print_stacktrace(frame.f_back, level)
        return

    print("%2d: %s@%s:%s => %s:%d"%(
        level,
        "  " * level * 0, # remove 0 to left-pad each frame

        # frame.f_lasti,
        frame.f_globals['__name__'],
        frame.f_code.co_name,

        frame.f_code.co_filename,
        frame.f_lineno,
    ))

    if (frame.f_back):
        print_stacktrace(frame.f_back, level + 1)


def lnotab(pairs, first_lineno=0):
    """Yields byte integers representing the pairs of integers passed in."""
    assert first_lineno <= pairs[0][1]
    cur_byte, cur_line = 0, first_lineno
    for byte_off, line_off in pairs:
        byte_delta = byte_off - cur_byte
        line_delta = line_off - cur_line
        assert byte_delta >= 0
        assert line_delta >= 0
        while byte_delta > 255:
            yield 255 # byte
            yield 0   # line
            byte_delta -= 255
        yield byte_delta
        while line_delta > 255:
            yield 255 # line
            yield 0   # byte
            line_delta -= 255
        yield line_delta
        cur_byte, cur_line = byte_off, line_off

def lnotab_string(pairs, first_lineno=0):
    return "".join(chr(b) for b in lnotab(pairs, first_lineno))

def byte_pairs(lnotab):
    """Yield pairs of integers from a string."""
    for i in range(0, len(lnotab), 2):
        yield lnotab[i], lnotab[i+1]
        
def lnotab_numbers(lnotab, first_lineno=0):
    """Yields the byte, line offset pairs from a packed lnotab string."""

    last_line = None
    cur_byte, cur_line = 0, first_lineno
    for byte_delta, line_delta in byte_pairs(lnotab):
        if byte_delta:
            if cur_line != last_line:
                yield cur_byte, cur_line
                last_line = cur_line
            cur_byte += byte_delta
        cur_line += line_delta
    if cur_line != last_line:        
        yield cur_byte, cur_line


class CoverageFile:

    __code = None

    def __init__(self, code):
        self.__line_exec = {}
        self.__line_active = []
        self.__code = code

    def line_tick(self, lineno):
        # print('tick', self, self.filename, lineno)
        if lineno in self.__line_exec:
            self.__line_exec[lineno] += 1
        else:
            self.__line_exec[lineno] = 1

    def __code_active_lines(self, code):
        for x in lnotab_numbers(code.co_lnotab, code.co_firstlineno):
            self.__line_active.append(x[1])

    def __code_recursive_active_lines(self, code):
        self.__code_active_lines(code)
        for const in code.co_consts:
            if type(const) == type(code):
                self.__code_recursive_active_lines(const)

    def gather_active_lines(self):
        self.__code_recursive_active_lines(self.__code)

    def dump(self):
        # print("Coverage stats for file:", self.filename)
        self.gather_active_lines()
        
        with open(self.filename, "r") as source:
            lineno = 0
            for line in source:
                lineno += 1
                line = line.rstrip("\r\n")
                prefix = " "*4
                if lineno in self.__line_active:
                    execno = 0
                    if lineno in self.__line_exec:
                        execno = self.__line_exec[lineno]
                    
                    prefix = "%4d"%(execno)
                print(prefix, line)

    def lines_execution(self):
        # print(self, self.__line_exec)
        return self.__line_exec

    def __get_filename(self):
        return self.__code.co_filename

    filename = property(__get_filename)

class Coverage:

    __files = {}

    def include_code(self, code):
        filename = code.co_filename
        if not code.co_name == '<module>':
            raise Exception("Expected '<module>' code but got:", code.co_name)

        if not filename in self.__files.keys():
            self.__files[filename] = CoverageFile(code)


    def line_tick(self, filename, lineno):
        if filename in self.__files:
            self.__files[filename].line_tick(lineno)

    def lines_execution(self):
        lines_execution = {"lines":{}}
        lines = lines_execution["lines"]
        for filename in self.__files:
            # print('collect',filename)
            # print('collect', self.__files[filename], self.__files[filename].lines_execution())
            l = list(self.__files[filename].lines_execution().keys())
            l.sort()
            lines[filename] = l
            del l
            
        
        return lines_execution

    def dump_all(self):
        for filename in self.__files:
            cov = self.__files[filename]
            cov.dump()

class _Prof:
    trace_count = 0;
    display_flags = 0
    DISPLAY_INSTRUCITON = 1<<0
    DISPLAY_STACKTRACE = 1<<1
    __coverage = Coverage()

    def trace_tick(self, frame, event, arg):
        self.trace_count += 1

        if event == 'call':
            if frame.f_code.co_name == '<module>':
                self.__coverage.include_code(frame.f_code)

        if event == 'line':
            self.__coverage.line_tick(frame.f_code.co_filename, frame.f_lineno)

        if self.display_flags & _Prof.DISPLAY_STACKTRACE:
            print_stacktrace(frame)

    def dump_coverage_stats(self):
        self.__coverage.dump_all()

    def coverage_data(self):
        return self.__coverage.lines_execution()

global __prof__
if not '__prof__' in globals():
    __prof__ = _Prof()
# __prof__.display_flags |= _Prof.DISPLAY_INSTRUCITON
__prof__.display_flags |= _Prof.DISPLAY_STACKTRACE


alice_handler_set = False
def trace_tick_handler_alice(frame, event, arg):
    # print("### frame_handler::alice event:", event)
    __prof__.trace_tick(frame, event, arg)
    return None

bob_handler_set = False
def trace_tick_handler_bob(frame, event, arg):
    # print("### frame_handler::bob event:", event)
    __prof__.trace_tick(frame, event, arg)
    return None

def trace_tick_handler(frame, event, arg):
    if frame.f_globals['__name__'].startswith('importlib.'):
        return
    
    # import sys
    # sys.exit(0)
    # print("### trace_handler event:", event)
    __prof__.trace_tick(frame, event, arg)

    # sys.settrace(trace_tick_handler)
    # if frame.f_trace_opcodes == False:
    #     frame.f_trace_opcodes = True

    global bob_handler_set
    if event == 'call' and  not bob_handler_set:
        bob_handler_set = True
        return trace_tick_handler_bob

    global alice_handler_set
    if event == 'call' and not alice_handler_set:
        alice_handler_set = True
        return trace_tick_handler_alice

    # return None
    return trace_tick_handler

def atexit_summary():
    print("\n------------------ script exited ------------------")
    print("Total traces executed: ", __prof__.trace_count)
    # __prof__.dump_coverage_stats()
    with open(".coverage","w") as f:
        # wtf so private much beautiful wow
        f.write("!coverage.py: This is a private format, don't read it directly!")
        # poormans json
        f.write(str(__prof__.coverage_data()).replace("'",'"'))
    

def factorial(n):
    if n == 0:
        # Display the bubbling stacktrace from this nested call.
        # __prof__.display_flags |= _Prof.DISPLAY_STACKTRACE
        return 1
    else:
        return n * factorial(n-1)

def factorials_up_to(x, b):
    a = 1
    for i in range(1, x+1):
        a = a * i
        print("inbetween bin_op")
        a = a + a
        yield a + b


exc = Exception('ExceptionallyLoud')
zero = 0

def do():
    # These commands are here to demonstrate some execution being traced.
    print("Who loves the sun?")

    import trace_generic
    trace_generic.run_tests()
    return

# Register atexit handler that will be executed before sys.exit().
if 'micropython' in globals():
    sys.uatexit(atexit_summary)
else:
    import atexit
    atexit.register(atexit_summary)

# Register the tracing callback.
sys.settrace(trace_tick_handler)

do()

sys.settrace(None)

print('nothing to trace here')

# Trigger the atexit handler.
# sys.exit()
# raise Exception('done')
# atexit()
