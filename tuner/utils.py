# -*- coding: utf-8 -*-

import time
import pickle
import logging
import datetime


def time_start():
    return time.time()


def time_end(start):
    end = time.time()
    delay = end - start
    return delay


def get_timestamp():
    """
    获取UNIX时间戳
    """
    return int(time.time())


def time_to_str(timestamp):
    """
    将时间戳转换成[YYYY-MM-DD HH:mm:ss]格式
    """
    return datetime.datetime.\
        fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


class Logger:

    def __init__(self, name, log_file=''):
        self.log_file = log_file
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        sh = logging.StreamHandler()
        self.logger.addHandler(sh)
        if len(log_file) > 0:
            self.log2file = True
        else:
            self.log2file = False

    def _write_file(self, msg):
        if self.log2file:
            with open(self.log_file, 'a+') as f:
                f.write(msg + '\n')

    def get_timestr(self):
        timestamp = get_timestamp()
        date_str = time_to_str(timestamp)
        return date_str

    def warn(self, msg):
        msg = "%s[WARN] %s" % (self.get_timestr(), msg)
        self.logger.warning(msg)
        self._write_file(msg)

    def info(self, msg):
        msg = "%s[INFO] %s" % (self.get_timestr(), msg)
        #self.logger.info(msg)
        self._write_file(msg)

    def error(self, msg):
        msg = "%s[ERROR] %s" % (self.get_timestr(), msg)
        self.logger.error(msg)
        self._write_file(msg)


def save_state_actions(state_action, filename):

    f = open(filename, 'wb')
    pickle.dump(state_action, f)
    f.close()
