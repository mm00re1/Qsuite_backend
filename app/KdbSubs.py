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
import time
from queue import Empty


config = load_config()
custom_ca = config['security']['custom_ca_path']

_conn_cache = {}
MAX_CONN_AGE = 60 * 60

def make_kdb_conn(host, port, tls, timeout, scope=""):
    """
    Creates or reuses a cached QConnection to KDB+.
    Reuses if it's less than MAX_CONN_AGE old; otherwise creates a new QConnection.
    """
    global _conn_cache
    key = (host, port, tls, scope)
    now = time.time()

    # If we have a cached connection, check whether it's still valid
    if key in _conn_cache:
        entry = _conn_cache[key]
        age = now - entry["time_opened"]

        # If age <= MAX_CONN_AGE, reuse existing QConnection
        if age <= MAX_CONN_AGE:
            return entry["conn"]
        else:
            # Otherwise, discard old connection and create a new one
            try:
                entry["conn"].close()  # Make sure it’s closed
            except:
                pass
            del _conn_cache[key]

    # We either have no cache entry or it was expired
    credentials = load_credentials()
    method = credentials.get('method')

    if method == 'User/Password':
        q = QConnection(
            host=host,
            port=port,
            username=credentials.get('username'),
            password=credentials.get('password'),
            tls_enabled=tls,
            timeout=timeout,
            custom_ca=custom_ca,
            pandas=True
        )
    elif method == 'Azure Oauth':
        oauth_config = {
            'tenant_id': credentials.get('tenant_id'),
            'client_id': credentials.get('client_id'),
            'client_secret': credentials.get('client_secret'),
            'scope': scope,
            'flow': 'client_credentials',
        }
        q = QConnection(
            host=host,
            port=port,
            username=credentials.get('username'),
            tls_enabled=tls,
            timeout=timeout,
            custom_ca=custom_ca,
            oauth_provider="azure",
            oauth_config=oauth_config,
            pandas=True
        )
    else:
        raise ValueError("Unsupported connection method.")

    # Store new connection in our cache
    _conn_cache[key] = {
        "conn": q,
        "time_opened": now
    }
    return q


def sendFreeFormQuery(code, host, port, tls, scope = ""):
    q = make_kdb_conn(host, port, tls, 10, scope)
    try:
        q.open()
        response = q.sendSync('.qsuite.executeUserCode', ''.join(code))
        return parseResponse(response, "Response Preview")

    except Exception as e:
        res = {"success":False, "data": "", "message": "Kdb Error => " + str(e), "type": "error"}

    finally:
        q.close() 


def sendFunctionalQuery(kdbFunction, host, port, tls, scope = ""):
    q = make_kdb_conn(host, port, tls, 10, scope)
    try:
        q.open()
        response = q.sendSync('.qsuite.executeFunction', kdbFunction)
        return parseResponse(response,"Response was not Boolean")

    except Exception as e:
        res = {"success":False, "data": "", "message": "Kdb Error => " + str(e)}

    finally:
        q.close()

def sendKdbQuery(kdbFunction, host, port, tls, scope = "", *args):
    q = make_kdb_conn(host, port, tls, 10, scope)
    q.open()
    res = q.sendSync(kdbFunction, *args)
    q.close()
    return res

def test_kdb_conn(host, port, tls, scope = ""):
    q = make_kdb_conn(host, port, tls, 5, scope)
    q.open()
    q.close()
    #throws exception if it times out or port doesn't exist
    return "success"

class kdbSub(threading.Thread):
    def __init__(self, sub_name, host, port, tls, scope = "", *args):
        super(kdbSub, self).__init__()
        self.q = make_kdb_conn(host, port, tls, 10, scope)
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
def clean_data(data):
    # clean data recursively - replacing Nan or Inf with None
    if isinstance(data, dict):
        return {k: clean_data(v) for k, v in data.items()}
    elif isindtance(data, list):
        return [clean_data(v) for v in data]
    elif isinstance(data, bytes):
        return data.decode('utf-8')
    elif isinstance(data, float) and (np.isnan(data) or np.isinf(data)):
        return None
    elif pd.isna(data):
        return None
    return data

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
    return {"columns": df_columns, "rows": clean_data(df_data), "trimmed": trimmed, "num_rows": len(data)}

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

    return clean_data(output)

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


def run_subscription_test(
    sub_name: str,
    kdb_host: str,
    kdb_port: int,
    kdb_tls: bool,
    kdb_scope: str,
    sub_params: list,
    number_of_messages: int = 5,
    timeout_seconds: int = 10
) -> dict:
    """
    Start a kdb subscription in a thread and gather messages until either
    we have the requested number of messages or we've reached the timeout.
    Returns a dict with success, message, and collected data.
    """
    q_thread = kdbSub(sub_name, kdb_host, kdb_port, kdb_tls, kdb_scope, *sub_params)
    q_thread.start()

    start_time = time.time()
    collected_messages = []
    success = False

    try:
        while True:
            # Check if we've hit the desired number_of_messages
            if len(collected_messages) >= number_of_messages:
                success = True
                break

            # Check if we've hit the timeout
            if time.time() - start_time >= timeout_seconds:
                # We can consider it a partial success or a fail, depending on your logic
                success = False
                break

            # Try to get data from the queue
            try:
                msg = q_thread.message_queue.get_nowait()
                collected_messages.append(msg)
            except Empty:
                pass

            # If the thread signaled a stop (e.g., error or server closed)
            if q_thread.stopped():
                # Decide if that is success or fail. Possibly it ended early?
                success = len(collected_messages) > 0
                break

            time.sleep(0.01)

    except Exception as e:
        print(f"Error running subscription: {str(e)}")
        return {
            "success": False,
            "message": f"Error: {str(e)}",
            "data": []
        }
    finally:
        # Always stop the thread if it's still running
        q_thread.stopit()

    return {
        "success": success,
        "message": f"Received {len(collected_messages)} messages."
                   + (" Timeout reached." if not success else ""),
        "data": collected_messages
    }
