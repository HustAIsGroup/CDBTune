### 环境

| 主机名   | ip             | 必装软件    | 功能               | 举例用户 | 密码   | 操作系统    | Python版本 |
| -------- | -------------- | ----------- | ------------------ | -------- | ------ | ----------- | ---------- |
| CDBTune1 | 192.168.110.10 | sysbench1.0 | 网络训练，主动压测 | cheng    | 123456 | Ubuntu16.04 | 2.7        |
| CDBTune2 | 192.168.110.11 | mysql5.6    | 数据库服务器       | cheng    | 123456 | Ubuntu16.04 | 2.7        |

### 搭建步骤

1. 将训练模型的项目AutoTuner放至两台服务器的用户cheng的home目录下，即目录为：/home/cheng/AutoTuner（项目名称请保持AutoTuner不变）。

2. 在CDBTune1安装sysbench1.0，安装方法参考：[Ubuntu安装sysbench1.0](https://blog.csdn.net/cxin917/article/details/81557453)。

3. 在CDBTune2安装mysql5.6（注意版本，是5.6！！！），root初始密码设置为123456。安装完成后，使用命令 sudo service mysql start 开启mysql服务。

   如何彻底删除mysql参考：[Ubuntu16.04彻底删除mysql](https://www.cnblogs.com/mjhblog/p/10499772.html)

   如何安装mysql5.6参考：[Ubuntu安装mysql5.6](https://blog.csdn.net/qq_36641556/article/details/80921737)

4. 在CDBTune2上登录mysql，创建一个database，名为sbtest（名字可以随便取，只不过需要修改源码中的两个脚本的数据库名）。

5. 给mysql的root用户开启远程访问权限。

   如何给mysql的root用户开启远程访问权限参考：[mysql给root开启远程访问权限](https://www.cnblogs.com/goxcheer/p/8797377.html)

6. 在mysql中，使用命令：

   ```mysql
   select name from innodb_metrics where status="enabled" order by name; 
   ```

   再使用如下命令将adaptive_hash_searches_btree这个向量开启：

   ```mysql
   set global innodb_monitor_enable = "adaptive_hash_searches_btree";
   ```

   打开计数器即可。具体计数器打开/关闭/重置可以参考：[mysql如何打开/关闭/重置计数器](https://www.cnblogs.com/yuyutianxia/p/7747035.html)

7. 在CDBTune1上使用sysbench对CDBTune2的sbtest进行初始化，使用的是/home/cheng/AutoTuner/scripts/prepare.sh脚本，首先用vim将prepare.sh中的script_path修改为："/usr/share/sysbench/" （注意最后有一个”/”）。之后使用命令：

   ```bash
   sh prepare.sh read 192.168.110.11 3306 123456
   ```

   （当前在/home/cheng/AutoTuner/scripts目录下）对CDBTune2的sbtest数据库建了8张表，每张表1000000条数据（这一步耗时可能会有点长，耐心等待即可）。

8. 对两台机器，都进行requirement.txt的安装（使用pip安装，注意不是pip3）。首先进入项目home目录，即/home/cheng/AutoTuner，再执行命令 

   ```bash
   pip install -r requirements.txt --user
   ```

   **若报错，可看报错解决。**

9. 在CDBTune2上安装pexpect，执行如下命令：

   ```bash
   pip install pexpect --user
   ```

10. 在CDBTune2的/home/cheng/AutoTuner/server目录下执行命令：

    ```bash
    sh ./start_server.sh
    ```

11. 在CDBTune2上输入命令:netstat -an | grep 20000  查看是否启动成功。

12. 在CDBTune1的/home/cheng/AutoTuner/tuner仿照CDBTune2的start_server.sh脚本，写一个start_train.sh的脚本。内容如下：

    ```bash
    #!/usr/bin/env bash
    
    nohup python train.py >> train.log &
    ```

13. 在CDBTune1使用pip安装enum。命令：

    ```bash
    pip install enum enum34
    ```

14. 在CDBTune1的/home/cheng/AutoTuner/environment/configs.py中添加CDBTune2的mysql信息（仿造已有的mysql格式进行填写），如下：

    ```python
    instance_config = {
        'mysql3': {
            'host': '192.168.110.11',
            'user': 'root',
            'passwd': '123456',
            'port': 3306,
            'database': 'sbtest',
            'memory': 34359738368
        }
    }
    ```

15. 在python2.x的环境安装sklearn，使用命令：

    ```shell
    pip install -U scikit-learn==0.19
    ```
    
16. 将CDBTune1的/home/cheng/AutoTuner/environment/mysql.py中的TEMP_FILES和PROJECT_DIR变量中的用户名改为”cheng”（服务器的用户名）。

17. 将CDBTune1的/home/cheng/AutoTuner/scripts/run_sysbench.sh中的script_path修改为"/usr/share/sysbench/"。

18. 需要自行设置environment模块下knobs.py文件中各个knob的默认值。

19. 修改/etc/mysql/my.cnf文件，将内容替换为如下：
    ~~~mysql
    # DEFAULT_VALUE为上一步在knobs.py中设置的默认值
    [mysqld]
    max_binlog_cache_size = DEFAULT_VALUE
    binlog_format = MIXED
    innodb_buffer_pool_size = DEFAULT_VALUE
    innodb_log_files_in_group = DEFAULT_VALUE
    innodb_log_file_size = DEFAULT_VALUE
    innodb_read_io_threads = DEFAULT_VALUE
    binlog_cache_size = DEFAULT_VALUE
    innodb_buffer_pool_instances = DEFAULT_VALUE
    binlog_checksum = NONE
    max_binlog_size = DEFAULT_VALUE
    skip_name_resolve = OFF
    innodb_write_io_threads = DEFAULT_VALUE
    innodb_purge_threads = DEFAULT_VALUE
    innodb_file_per_table = OFF
    table_open_cache = DEFAULT_VALUE
    max_connections = DEFAULT_VALUE
    
    [mysqld_safe]
    
    [mysqldump]
    max_allowed_packet = 16M
    ~~~

19. 需要自行设置tuner模块下tuner_configs.py中的一些超参数的值。

20. 运行CDBTune1的tuner/train.py文件，可以指定代码里提供的参数，不指定则按默认参数运行，开始训练model。

21. 模型训练完成后，运行CDBTune1的tuner/evaluate.py文件，对模型进行评估。同时必须指定params参数，参数值为tuner/model_params下的文件名部分前缀，如下：
    ~~~shell
    python2 evaluate.py --params train_ddpg_1571382343_4600
    ~~~
### 报错解决

**Q:** 在CDBTune2安装mysql后，使用命令mysql -u root -p并且正确输入密码后报错：ERROR 2002 (HY000): Can't connect to local MySQL server through socket '/var/run/mysqld/mysqld.sock' (2)。

**A:** mysql服务没有开启，使用命令sudo service mysql start开启服务再登录mysql即可。

 

**Q:** 在/home/cheng/AutoTuner/scripts下使用命令sh ./prepare.sh read 192.168.110.11 3306 123456 打算对sbtest进行初始化，报错：./prepare.sh: 5: [: read: unexpected operator   ./prepare.sh: 8: [: read: unexpected operator。

**A: **由于ubuntu的sh默认为dash，而脚本使用的是bash，所以将sh改为bash即可。或者永久修改使得sh->bash，参考：[如何永久使sh指向bash](https://blog.csdn.net/hjxu2016/article/details/83867246)。

 

**Q:** 安装requirement.txt的MySQL-python==1.2.3报错：Command "python setup.py egg_info" failed with error code 1 in /tmp/pip-build-_pzcr1qo/MySQL-python/。

**A:** 使用pip安装容易出错，使用以下两个命令安装MySQL-python：sudo apt-get install libmysql++-dev;sudo easy_install MySQL-python.参考：[安装MySQLdb发生EnvironmentError: mysql_config not found](https://blog.csdn.net/xgocn/article/details/82893266)。安装成功后，删除requirement.txt中的第一行，再使用pip安装requirement.txt。

**Q:** 报错：Setup script exited with error: command 'x86_64-linux-gnu-gcc' failed with exit status 1。
**A:** 原因是缺少依赖。参考：[解决Python缺少依赖](https://blog.csdn.net/u012798683/article/details/88403066)解决方法。
