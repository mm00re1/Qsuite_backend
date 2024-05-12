from qpython.qconnection import QConnection
import numpy
import threading
from qpython.qtype import QException
from qpython.qcollection import QTable
from queue import Queue
import numpy as np

def sendKdbQuery(kdbFunction, host, port, *args):
    q = QConnection(host=host, port=port, timeout = 10)
    q.open()
    try:
        response = q.sendSync(kdbFunction, *args)
        #if res is not a boolean
        print("kdb response")
        print(response)
        print(type(response))
        print(type(response) is np.bool_)
        if type(response) is np.bool_:
            if response:
                res = {"success": True, "data": "", "message": "Test Ran Successfully"}
            else:
                res = {"success": False, "data": "", "message": "Test Failed"}
        else:
            res = {"success": False, "data": str(response), "message": "Response Preview"}
    except Exception as e:
        res = {"success":False, "data": "", "message": "Kdb Error => " + str(e)}
    q.close() 
    return res

class kdbSub(threading.Thread):
    def __init__(self, tbl, index, kdb_host, kdb_port):
        super(kdbSub, self).__init__()
        self.q = QConnection(host=kdb_host, port=kdb_port)
        self.q.open()
        self.q.sendSync('.u.sub', numpy.string_(tbl), numpy.string_(index))
        self.message_queue = Queue()
        self._stopper = threading.Event()

    def stopit(self):
        print("unsubbing")
        print("closing conn")
        self.q.close()
        ###self.q.sendAsync(".u.unsub","direct unsub")  --> unsub logic is also handled in .z.pc
        self._stopper.set()

    def stopped(self):
        return self._stopper.is_set()

    def run(self):
        while not self.stopped():
            try:
                message = self.q.receive(data_only = False, raw = False) # retrieve entire message
                if isinstance(message.data, list):
                    # unpack upd message
                    if len(message.data) == 3 and message.data[0] == b'upd' and isinstance(message.data[2], QTable):
                        for row in message.data[2]:
                            self.message_queue.put(row)

            except QException as e:
                print("****Error reading q message, error***: " + str(e))


##utility functions##
def parseKdbTableWithSymbols(table):
    bstr_cols = table.select_dtypes([object]).columns
    for i in bstr_cols:
        table[i] = table[i].apply(lambda x: x.decode('latin'))

def parseKdbListWithSymbols(data):
    return [x.decode('latin') for x in data]
