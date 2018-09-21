# trace-browser

Quickly hacked together, a PyQt5 application that allows you to browse
Python traces (or any traces) in `.jsonl` format.

![Screenshot](https://i.imgur.com/OThOFwK.png)

In Python, you can trace files like this:

```python
class Tracer(object):

  def __init__(self, filename, append=False, record_locals=False):
    self.filename = filename
    self.file = open(filename, 'a' if append else 'w')
    self.lock = threading.Lock()
    self.enabled = False
    self.record_locals = record_locals

  def enable(self):
    if self.enabled: return
    self.enabled = True

    @wraps(thread.start_new_thread)
    def start_new_thread(func, args, kwargs={}):
      @wraps(func)
      def wrapper(*args, **kwargs):
        sys.settrace(self._handle_trace)
        return func(*args, **kwargs)
      return start_new_thread.__wrapped__(wrapper, args, kwargs)

    thread.start_new_thread = start_new_thread
    threading._start_new_thread = start_new_thread
    sys.settrace(self._handle_trace)

  def disable(self):
    if not self.enabled: return
    self.enabled = False
    thread.start_new_thread = thread.start_new_thread.__wrapped__
    threading._start_new_thread = thread._start_new_thread.__wrapped__
    sys.settrace(None)

  def _handle_trace(self, frame, event, arg, depth=0):
    data = {'timestamp': time.clock(), 'event': event, 'arg': safe_repr(arg),
            'thread': thread.get_ident(), 'filename': frame.f_code.co_filename,
            'lineno': frame.f_lineno, 'co_name': frame.f_code.co_name,
            'depth': depth}
    if self.record_locals:
      data['locals'] = json.dumps(frame.f_locals, cls=SafeJsonEncoder)
    with self.lock:
      self.file.write(json.dumps(data))
      self.file.write('\n')
      self.file.flush()
    if event == 'call':
      return functools.partial(self._handle_trace, depth=depth+1)
    return frame.f_trace or self._handle_trace

Tracer('trace.jsonl', append=False).enable()
```
