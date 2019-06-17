print("Yep, I got imported.")

try:
    from micropython import const
    import micropython

    _WTF = "WTF"
    _CNT = const(123)
    A123 = const(123)
    a123 = const(123)
except Exception as e:
    pass

def dummy():
    return False

def saysomething():
    print("There, I said it.")

def neverexecuted():
    print("Never got here!")

print("Yep, got here")