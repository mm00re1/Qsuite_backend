from qpython.qconnection import QConnection
import threading
from qpython.qtype import QException
from qpython.qcollection import QTable
from queue import Queue
import numpy as np
from custom_config_load import *
from encryption_utils import load_credentials
import select
import pandas as pd
from qpython.qcollection import QDictionary


config = load_config()
custom_ca = config['security']['custom_ca_path']

def make_kdb_conn(host, port, tls, timeout):
    credentials = load_credentials()
    method = credentials.get('method')
    if method == 'User/Password':
        username = credentials.get('username')
        password = credentials.get('password')
        return QConnection(host=host, port=port, username = username, password = password, tls_enabled=tls, timeout = timeout, custom_ca = custom_ca, pandas = True)
    #elif method == 'Azure Oauth':
        # add proper logic later
        #client_id = credentials.get('client_id')
        #client_secret = credentials.get('client_secret')
        # Use client_id and client_secret to obtain token and connect
        #return QConnection(host=host, port=port, tls_enabled=tls, timeout = 10, custom_ca = custom_ca)
    else:
        raise ValueError("Unsupported connection method.")
    # ....


def sendFreeFormQuery(code, host, port, tls):
    q = make_kdb_conn(host, port, tls, 10)
    try:
        q.open()
        response = q.sendSync('.qsuite.executeUserCode', ''.join(code))
        return parseResponse(response, "Response Preview")

    except Exception as e:
        res = {"success":False, "data": "", "message": "Kdb Error => " + str(e), "type": "error"}

    finally:
        q.close() 


def sendFunctionalQuery(kdbFunction, host, port, tls):
    q = make_kdb_conn(host, port, tls, 10)
    try:
        q.open()
        response = q.sendSync('.qsuite.executeFunction', kdbFunction)
        return parseResponse(response,"Response was not Boolean")

    except Exception as e:
        res = {"success":False, "data": "", "message": "Kdb Error => " + str(e)}

    finally:
        q.close()

def sendKdbQuery(kdbFunction, host, port, tls, *args):
    q = make_kdb_conn(host, port, tls, 10)
    q.open()
    res = q.sendSync(kdbFunction, *args)
    q.close()
    return res

def test_kdb_conn(host, port, tls):
    q = make_kdb_conn(host, port, tls, 5)
    q.open()
    q.close()
    #throws exception if it times out or port doesn't exist
    return "success"

class kdbSub(threading.Thread):
    def __init__(self, sub_name, host, port, tls, *args):
        super(kdbSub, self).__init__()
        self.q = make_kdb_conn(host, port, tls, 10)
        self.q.open()
        self.q.sendSync('.qsuite.subTests.' + sub_name, *args)
        self.message_queue = Queue()
        self._stopper = threading.Event()

    def stopit(self):
        print("KdbSubs - unsubbing")
        self._stopper.set()           # <--- signal thread first
        ###self.q.sendAsync(".u.unsub","direct unsub")  --> unsub logic is also handled in .z.pc

    def stopped(self):
        return self._stopper.is_set()

    def run(self):
        try:
            while not self.stopped():
                # Check if the socket has data ready to read with a timeout (1 second)
                ready_to_read, _, _ = select.select([self.q._connection], [], [], 1.0)

                # If data is available, read it
                if ready_to_read:
                    message = self.q.receive(data_only=False, raw=False)
                    if isinstance(message.data, list):
                        if len(message.data) == 3 and message.data[0] == b'upd':
                            self.message_queue.put(parse_dataframe(message.data[2]))
                else:
                    # No data received within the timeout, continue looping
                    #print("No data received, checking stop condition...")
                    continue

        except Exception as e:
            print("Error encountered while trying to read tick message: ", e)
        finally:
            self.q.close()
            print("KdbSubs - finished closing conn")


##utility functions##
def parseKdbTableWithSymbols(table):
    bstr_cols = table.select_dtypes([object]).columns
    for i in bstr_cols:
        table[i] = table[i].apply(lambda x: x.decode('latin'))

def parseKdbListWithSymbols(data):
    return [x.decode('latin') for x in data]

def parse_dataframe(data):
    max_rows = 12
    trimmed = len(data) > max_rows
    df_data = data.head(max_rows).to_dict(orient='records')
    df_columns = list(data.columns)
    return {"columns": df_columns, "rows": df_data, "trimmed": trimmed, "num_rows": len(data)}

def parseResponse(data, err_message):
    #if result is a boolean
    if type(data) is np.bool_:
        if data:
            return {"success": True, "data": "", "message": "Test Ran Successfully", "type": "bool"}
        else:
            return {"success": False, "data": "", "message": "Test Failed", "type": "bool"}

    elif isinstance(data, QDictionary):
        return {"success": False, "data": parse_q_dictionary(data), "message": err_message, "type": "dictionary"}

    elif isinstance(data, pd.DataFrame):
        return {"success": False, "data": parse_dataframe(data), "message": err_message, "type": "dataframe"}

    # 3) Other data types (numpy array, list, dictionary, etc.)
    else:
        # Catch-all: convert the response to a string. Optionally preview only part of it.
        string_data = convert_value_to_str(data)
        if len(string_data) > 400:
            string_data = string_data[:400] + " ......"

        return {"success": False, "data": string_data, "message": "Response Preview", "type": "string"}


def parse_q_dictionary(qdict):
    max_keys = 10
    max_chars = 40
    output = []

    keys_list = qdict.keys
    values_list = qdict.values

    for i, (key, val) in enumerate(zip(keys_list, values_list)):
        # Only process up to 10 keys
        if i >= max_keys:
            break

        # Convert key -> string, then truncate if needed
        key_str = str(key) if not isinstance(key, (bytes, np.bytes_)) else key.decode('utf-8')
        if len(key_str) > max_chars:
            key_str = key_str[:max_chars] + "..."

        # Convert the value to a single string
        val_str = convert_value_to_str(val)
        if len(val_str) > max_chars:
            val_str = val_str[:max_chars] + "..."

        output.append({"key": key_str, "value": val_str})

    return output

def convert_value_to_str(val):
    """
    Convert the given value to a single string.
    For arrays/Series, join them; for scalars, just str() them.
    """
    # If it's a numpy scalar (e.g. np.int64), convert to Python type
    if isinstance(val, (bytes, np.bytes_)):
        return val.decode('utf-8')

    # If it's a Pandas Series, join with spaces
    if isinstance(val, pd.Series):
        items = [convert_value_to_str(x) for x in val]
        return "(" + "; ".join(x for x in items) + ")"

    # If it's a list, join with spaces
    if isinstance(val, list):
        items = [convert_value_to_str(x) for x in val]
        return "(" + "; ".join(x for x in items) + ")"

    if hasattr(val, 'item'):
        return str(val.item())

    # Fallback: just string-cast it
    return str(val)


