# Copyright (c) 2018  Niklas Rosenstein
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.


from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

import argparse
import collections
import itertools
import functools
import json
import math
import sys
assert sys.version >= '3.3'


def create_colors(num):
  current_hue = 0.0
  for _ in range(num or 2):
    yield QColor.fromHslF(current_hue, 1.0, 0.8)
    current_hue = (current_hue + 0.618033988749895) % 1.0


class TraceTimeline(QWidget):

  scrollPositionChanged = pyqtSignal()

  def __init__(self, traces):
    super().__init__()
    self._traces = traces
    self._threads = []
    for t in self._traces:
      if t['thread'] not in self._threads:
        self._threads.append(t['thread'])
    self._colors = list(create_colors(len(self._threads)))

    self._scroll_pos = len(self._traces) - 1
    self._scroll_window = 1

  def setScrollWindow(self, num_traces):
    self._scroll_window = num_traces
    self.repaint()

  def setScrollPosition(self, trace_num):
    if trace_num < 0:
      trace_num = 0
    elif trace_num > len(self._traces):
      trace_num = len(self._traces)
    self._scroll_pos = trace_num
    self.repaint()

  def getScrollPosition(self):
    return self._scroll_pos

  def getColorForThread(self, thread):
    index = self._threads.index(thread)
    return self._colors[index]

  def getThreadList(self):
    return self._threads

  def minimumSizeHint(self):
    return QSize(len(self._threads) * 20, 100)

  def paintEvent(self, event):
    if not self._traces:
      return

    rect = event.rect()
    column_width = rect.width() / len(self._threads)
    node_height = rect.height() / len(self._traces)

    painter = QPainter()
    painter.begin(self)

    painter.fillRect(rect, QBrush(QColor('#444'), Qt.SolidPattern))

    brushes = [QBrush(color, Qt.SolidPattern) for color in self._colors]
    for idx, trace in enumerate(self._traces):
      column = self._threads.index(trace['thread'])
      painter.setPen(QPen(brushes[column], 1.0))
      x1 = column_width * column + column_width * 0.5
      y1 = idx * node_height
      y2 = (idx + 1) * node_height
      painter.drawLine(QLine(x1, y1, x1, y2))

    scroll_pos = self._scroll_pos / len(self._traces) * rect.height()
    scroll_window = self._scroll_window / len(self._traces) * rect.height()

    x1, x2 = 0, rect.width()
    painter.setPen(QPen(QBrush(QColor('#3AF'), Qt.SolidPattern), 1.0))
    painter.drawLine(QLine(x1, scroll_pos, x2, scroll_pos))

    visible_area = QRect(
      rect.left(),
      rect.top() + scroll_pos,
      rect.width(),
      scroll_window
    )
    if visible_area.top() < rect.top():
      visible_area.moveTop(rect.top())
    painter.fillRect(visible_area, QBrush(QColor(200, 200, 200, 127), Qt.SolidPattern))

    painter.end()

  def mousePressEvent(self, event):
    self._mouse_down = True
    self.mouseMoveEvent(event)

  def mouseMoveEvent(self, event):
    if self._mouse_down:
      self.setScrollPosition(int(event.y() / self.size().height() * len(self._traces)))
      self.scrollPositionChanged.emit()

  def mouseReleaseEvent(self, event):
    self._mouse_down = False


class TraceListView(QWidget):

  resized = pyqtSignal(object)

  def __init__(self, traces, thread, color):
    super().__init__()
    self._traces = traces
    self._thread = thread
    self._color = color
    self._offset = 1

  def _trace_to_string(self, trace):
    if trace['event'] == 'call':
      return '{}() {}:{}'.format(trace['co_name'], trace['filename'], trace['lineno'])
    else:
      return '[{}] {}:{}'.format(trace['event'], trace['filename'], trace['lineno'])

  def setOffset(self, offset):
    self._offset = offset
    self.repaint()

  def getNumDisplayTraces(self):
    fm = QFontMetrics(QFont())
    return int(math.ceil(self.size().height() / fm.height()))

  def minimumSizeHint(self):
    return QSize(10, 10)

  def paintEvent(self, event):
    rect = event.rect()
    painter = QPainter()
    painter.begin(self)
    painter.fillRect(rect, self._color)

    padding = 2
    fh = QFontMetrics(QFont()).height()
    lh = fh + padding * 2

    yoff = rect.top()
    for i, trace in enumerate(itertools.islice(self._traces, self._offset, len(self._traces))):
      i += self._offset
      if i % 2 == 1:
        painter.fillRect(QRect(0, yoff, rect.width(), lh), QBrush(QColor(0, 0, 0, 25), Qt.SolidPattern))
      if trace['thread'] == self._thread:
        painter.drawText(padding + trace['depth'] * 10, yoff - fh/2 + padding, self._trace_to_string(trace))
        if yoff >= rect.bottom():
          break
      yoff += lh

    painter.end()

  def resizeEvent(self, event):
    self.resized.emit(event)


class TraceExplorer(QWidget):

  def __init__(self, traces):
    super().__init__()
    self.setWindowTitle('Trace Explorer')
    self._traces = traces
    self._timeline = TraceTimeline(traces)
    self._timeline.scrollPositionChanged.connect(self._scroll_position_changed)
    self._scroll_content = QWidget()
    self._scroll_layout = QHBoxLayout(self._scroll_content)
    self._scroll_content.setLayout(self._scroll_layout)
    self._scroll_layout.setContentsMargins(0, 0, 0, 0)
    self._scroll_layout.setSpacing(0)
    self._views = []

    layout = QHBoxLayout(self)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addWidget(self._scroll_content, 1)
    layout.addWidget(self._timeline)

    def listview_resized(view, event):
      self._timeline.setScrollWindow(view.getNumDisplayTraces())

    # Start and end index of the selected trace nodes.
    for thread in self._timeline.getThreadList():
      color = self._timeline.getColorForThread(thread)
      color = QColor.fromHslF(color.hslHueF(), 1.0, 0.8)  # brighten up
      view = TraceListView(self._traces, thread, color)
      view.resized.connect(functools.partial(listview_resized, view))
      self._views.append(view)
      self._scroll_layout.addWidget(view)

  def _scroll_position_changed(self):
    for view in self._views:
      view.setOffset(self._timeline.getScrollPosition())



def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('file', help='The JSON-Lines file to explore.')
  parser.add_argument('-n', type=int, default=1000, help='The number traces '
      'to include in the explorer from the end of the file. Defaults to 1000.')
  args = parser.parse_args()

  print('Loading traces ...')
  traces = []
  with open(args.file) as fp:
    lines = collections.deque(maxlen=args.n)
    for line in fp:
      if line: lines.append(line)
    for line in lines:
      try: traces.append(json.loads(line))
      except ValueError as e:
        print(e)

  threads = collections.defaultdict(int)
  for trace in traces:
    trace['depth'] = threads[trace['thread']]
    if trace['event'] in ('call', 'c_call'):
      threads[trace['thread']] += 1
    elif trace['event'] in ('return', 'c_return') and trace['depth'] > 0:
      threads[trace['thread']] -= 1

  print('Starting TraceExplorer ...')
  app = QApplication(sys.argv)
  wnd = TraceExplorer(traces)
  wnd.show()
  app.exec_()


if __name__ == '__main__':
  main()
