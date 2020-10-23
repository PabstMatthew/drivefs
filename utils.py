DEBUG = True

def dbg(msg, end='\n'):
    if DEBUG:
        print('[DBG] '+msg, end=end)

def err(msg):
    print('[ERR] '+msg)
    assert False

