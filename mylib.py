#!/usr/bin/python3

import json
import logging
import requests
import socket
import sys
import time


class InfoFilter(logging.Filter):
  """Filter the StreamHandler output for typical stdout levels."""
  def filter(self, rec):
    return rec.levelno in (logging.DEBUG, logging.INFO)


def get_url(url, headers={}, attempts=5):
  if not headers:
    headers = {'User-Agent': user_agent()}
  logging.info('Loading %s', url)
  for attempt in range(attempts+1):
    try:
      response = requests.get(url, headers=headers, timeout=2)
      return response.text.strip()
    except requests.exceptions.ConnectionError:
      logging.error('Connection Error for %s.', url)
      time.sleep(attempt*2)
    except requests.exceptions.ReadTimeout:
      logging.error('URL read timeout for %s.', url)
  logging.error('Connection retries exhausted for %s.', url)
  return ''


def humanize(n: float, suffix: str='bps'):
    n = round(n)
    for unit in ' KMG':
      if abs(n) < 1024:
        return '%d%s%s' % (n, unit, suffix)
      n >>= 10


def setup_logging(logfile: str):
  log_formatter = logging.Formatter(
      '%(levelname).1s%(asctime)s %(filename)s:%(lineno)d]  %(message)s',
      datefmt='%Y-%m-%d_%H:%M:%S')
  logger = logging.getLogger()
  logger.setLevel(logging.DEBUG)

  # Log eveything to a file.
  file_handler = logging.FileHandler(logfile)
  file_handler.setFormatter(log_formatter)

  # Print stdout levels to stdout.
  stdout_handler = logging.StreamHandler(sys.stdout)
  stdout_handler.setFormatter(log_formatter)
  stdout_handler.addFilter(InfoFilter())

  # Print stderr levels to stderr (to be emailed via the cron output).
  stderr_handler = logging.StreamHandler()
  stderr_handler.setFormatter(log_formatter)
  stderr_handler.setLevel(logging.WARNING)

  logger.addHandler(file_handler)
  logger.addHandler(stdout_handler)
  logger.addHandler(stderr_handler)


def write_graphite(data: list, prefix: str='', port: int=2003,
                   server: str='127.0.0.1'):
  datafile = '/opt/graphite_data.txt'
  try:
    with open(datafile) as f:
      entries = f.read().splitlines()
  except:
    entries = []
  if entries:
    logging.debug('Previously unwritten graphite data is %d entries long.',
                 len(entries))
  sock = socket.socket()
  sock.settimeout(5)
  now = int(time.mktime(time.localtime()))
  for name, value in data:
    if prefix:
      metric = '%s.%s' % (prefix, name)
    else:
      metric = name
    entries.append('%s %s %d.' % (metric, value, now))
  try:
    sock.connect((server, port))
    connected = True
    logging.info('Connected to graphite.')
  except socket.error as error:
    connected = False
    logging.error('ERROR couldnt connect to graphite: %s', error)
    logging.error('Queueing data for later writing...')
  if connected:
    msg = bytes('\n'.join(entries) + '\n', 'ascii')
    sock.sendall(msg)
    logging.info('Wrote %d entries.', len(entries))
    entries = []
  if connected:
    sock.close()
  else:
    with open(datafile, 'w') as f:
      f.write('\n'.join(entries))


def telegram(creds: str, msg: str):
  with open(creds) as f:
    data = json.load(f)
  bot_id = data['bot_id']
  chat_id = data['chat_id']
  requests.post('https://api.telegram.org/bot%s/sendMessage' % bot_id,
      params = {
        'chat_id': chat_id,
        'disable_web_page_preview': True,
        'text': msg})


def user_agent():
  with open('/opt/user_agent.txt') as f:
    return f.read().strip()
