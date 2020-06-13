# -*- coding: utf-8 -*-
"""
Configure Server
"""

import os
import time
import pexpect
import platform
import argparse
import ConfigParser as CP
from SimpleXMLRPCServer import SimpleXMLRPCServer

docker = False


def get_state():
    check_start()
    m = os.popen('service mysql status')
    s = m.readlines()[2]
    s = s.split(':')[1].replace(' ', '').split('(')[0]
    if s == 'failed':
        return -1
    return 1


def check_start():
    a = sudo_exec('sudo tail -1 /var/log/mysql/ubunturmw.err', '123456')
    a = a.strip('\n\r')
    if a.find('pid ended') != -1:
        sudo_exec('sudo service mysql start', '123456')


def sudo_exec(cmdline, passwd):
    osname = platform.system()
    if osname == 'Linux':
        prompt = r'\[sudo\] password for %s: ' % os.environ['USER']
    elif osname == 'Darwin':
        prompt = 'Password:'
    else:
        assert False, osname
    child = pexpect.spawn(cmdline)
    idx = child.expect([prompt, pexpect.EOF], 3)
    if idx == 0:
        child.sendline(passwd)
        child.expect(pexpect.EOF)
    return child.before


def start_mysql(instance_name, configs):
    """
    Args:
        instance_name: str, MySQL Server Instance Name eg. ["mysql1", "mysql2"]
        configs: str, Formatted MySQL Parameters, e.g. "name:value,name:value"
    """

    params = configs.split(',')

    if docker:
        _params = ''
        for param in params:
            pair_ = param.split(':')
            _params += ' --%s=%s' % (pair_[0], pair_[1])
        sudo_exec('sudo docker stop %s' % instance_name, '123456')
        sudo_exec('sudo docker rm %s' % instance_name, '123456')
        time.sleep(2)
        cmd = 'sudo docker run --name mysql1 -e MYSQL_ROOT_PASSWORD=12345678 ' \
              '-d -p 0.0.0.0:3365:3306 -v /data/{}/:/var/lib/mysql mysql:5.6 {}'.format(instance_name, _params)
        print(cmd)
        sudo_exec(cmd, '123456')
    else:
        write_cnf_file(params)
        sudo_exec('sudo service mysql restart', '123456')
    time.sleep(5)
    return 1


def write_cnf_file(configs):
    """
    Args:
        configs: str, Formatted MySQL Parameters, e.g. "--binlog_size=xxx"
    """
    cnf_file = '/etc/mysql/my.cnf'
    config_parser = CP.ConfigParser()
    sudo_exec('sudo chmod 777 %s' % cnf_file, '123456')
    time.sleep(2)
    config_parser.read(cnf_file)
    for param in configs:
        pair_ = param.split(':')
        config_parser.set('mysqld', pair_[0], pair_[1])
    config_parser.write(open(cnf_file, 'w'))
    sudo_exec('sudo chmod 744 %s' % cnf_file, '123456')
    time.sleep(2)


def serve():

    server = SimpleXMLRPCServer(('0.0.0.0', 20000))
    server.register_function(start_mysql)
    server.register_function(get_state)
    server.serve_forever()


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--docker', action='store_true')
    opt = parser.parse_args()
    if opt.docker:
        docker = True

    serve()

