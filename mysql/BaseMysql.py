# -*- coding=utf-8 -*-
try:
    import MySQLdb
    import json
    import time
    from os.path import realpath
except Exception as e:
    print('\033[1;31;0m'+"[Import Error]:"+'\033[0m'+" The imported modules are not exist: "+str(e))


# MyDQLdb操作类的基本封装，对MySQL操作流程进行统一封装
# 实现基本的增删改查
class BaseMysql(object):
    # 数据库连接对象
    _conn = None

    # 当前操作的数据表名称
    _table = None

    # select-SQL
    _select_sql = "SELECT {cols} FROM {table} WHERE {where} "

    # insert-SQL
    _insert_sql = "INSERT IGNORE INTO {table}({cols}) values({values}) "

    #update-SQL
    _update_sql = "UPDATE {table} {sets} WHERE {where} "

    #insert_update-SQL
    _insert_update_sql = "INSERT INTO {table}({cols}) values({values}) ON DUPLICATE KEY UPDATE {updates} "

    #delete-SQL
    _delete_sql = "DELETE FROM {table} WHERE {where}"

    rowcount = 0

    description = (None, None, None, None, None, None, None)
    def __init__(self, *args, **kwargs):
        # 表结构临时文件保存位置
        self._temp_dir = None
        if args or kwargs:
            self._conn_args = args
            self._conn_kwargs = kwargs

    def _connect(self,  *args, **kwargs):
        """
        连接数据库
        常用的连接参数：host port user passwd db charset
        """
        if not self._conn:
            self._conn = MySQLdb.connect(*args, **kwargs)
        self._cursor = self._conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)
        return self._conn

    def _del_table(self, table):
        """
        处理数据库表名
        """
        if self._table:
            return self._table
        if table and isinstance(table, str):
            self._table = table
        else:
            raise SQLException("table name must be a string,but local table name is :"+str(table))

    def _del_col(self, cols):
        """
        把列字典转换成字符串
        :param cols: 可选参数，查询的列字典，默认为"*"
        该参数接受一个list
        eg：['id', 'name', 'gread g']    表示查询id, name, gread三列数据，其中gread设置别名为“g”,写法可以为“列名 别名”或“列名 AS 别名”

        :return: 列字符串
        """
        if cols == None:
            return "*"
        else:
            return ",".join(cols)

    def _where_add_marks(self, value):
        """
        为SQL where部分的值添加引号
        eg：“!=张三”转化成 “!='张三'”
        """
        mark = value[1:2]
        if mark == '=':
            mark = 2
        else:
            mark = 1
        if value[0:4] == 'like':
            mark = 4
        return value[0:mark] + " '" + value[mark:].strip() + "'"

    def _del_where(self, where):
        """
        处理where条件
        :param where: 可选参数，查询条件。默认为"true",不限制查询条件，该参数接受一个字典
        eg：{and : { id : ">5" , 'or' : { 'name' : '!="张三"'} }}  该条件等于 ： (id>5 or name!='张三')
        :return: where字符串
        """
        if where == None:
            return 'true'
        else:
            wstr = ''
            for key in where:
                if isinstance(where[key], dict):
                    if wstr == '':
                        wstr += " " + self._del_where(where[key])
                    else:
                        wstr += " " + key + " " + self._del_where(where[key])
                else:
                    wstr += " " + key + " " + self._where_add_marks(where[key])

            return "(" + wstr + " )"

    def _del_group(self, group):
        """
        处理分组 条件
        :param group: 可选参数，查询分组，默认不分组,该参数接受一个list或tuple
        eg：（'id','name'）    表示以id和name分组
        :return: 分组字符串
        """
        if group == None:
            return False
        else:
            return ",".join([key +" "+ group[key] for key in group])

    def _del_having(self, having):
        """
        处理orderby子句的having选项
        """
        return self._del_where(having)

    def _del_order(self, order):
        """
        处理order选项
        """
        if isinstance(order,dict):
            return self._del_group(order)
        else:
            return ",".join([str(key+1)+" "+item for key, item in enumerate(order)])

    def _del_limit(self, limit):
        """
        处理limit选项
        :param limit: 可选参数，限制数据量或分页，默认不惜限制，输出所以查询数据，该参数接受一个大于0的整数，或者一个二值list或tuple
        eg：10   表示只显式查询结果的前10条数据
        eg：(2, 10)  表示输出第二页的10条数据
        """
        if isinstance(limit, int):
            return str(limit)
        page = limit[0]
        line = limit[1]
        if isinstance(page, int) and isinstance(line, int):
            return str(page)+","+str(line)
        else:
            raise SQLException("Limit must be an integer or two value integer tuple or list which value must greater than zero")

    def select(self, table=None, cols=None, where=None, group=None, order=None, having=None, limit=None, console=False):
        """
        查询数据库
        :param table: 表名

        :param cols: 可选参数，查询的列字典，默认为"*"
        该参数接受一个list
        eg：['id', 'name', 'gread g']    表示查询id, name, gread三列数据，其中gread设置别名为“g”,写法可以为“列名 别名”或“列名 AS 别名”

        :param where: 可选参数，查询条件。默认为"true",不限制查询条件，该参数接受一个字典
        eg：{and : { id : ">5" , 'or' : { 'name' : '!="张三"'} }}  该条件等于 ： (id>5 or name!='张三')

        :param group: 可选参数，查询分组，默认不分组,该参数接受一个字典
        eg：（'id':"DESC",'name':"ASC"）    表示以id和name分组

        :param order: 可选参数，排序
        该参数接受一个字典或者列表
        eg：['desc','asc']   表示以第一列降序，第二列升序排列
        eg：{id : 'desc', name : 'asc'}  表示以id降序 name 升序排列

        :param having: 可选参数，

        :param limit: 可选参数，限制数据量或分页，默认不惜限制，输出所以查询数据，该参数接受一个大于0的整数，或者一个二值list或tuple
        eg：10   表示只显式查询结果的前10条数据
        eg：(2, 10)  表示输出第二页的10条数据

        :param console:是否输出SQL字符串，True时输出不执行SQL，False时执行SQL
        :return:字典数据
        """
        self._del_table(table)
        cols = self._del_col(cols)
        where = self._del_where(where)
        sql = self._select_sql.format(
            cols=cols,
            table = table or self._table,
            where= where
        )
        if group:
            sql += " GROUP BY "+self._del_group(group)
        if having:
            sql +=" HAVING "+self._del_having(having)
        if order:
            sql += " ORDER BY " + self._del_order(order)
        if limit:
            sql += " LIMIT "+self._del_limit(limit)
        if console:
            return sql
        else:
            return self.exec_sql(sql)

    def insert(self, table=None, cols=None, console=False):
        """
        插入数据
        :param table: 插入数据表名
        :param cols: 插入字段
        :param console: 是否打印SQL语句
        :return: sql语句或者插入结果
        """
        self._del_table(table)
        if not cols:
            raise SQLException("cols and values must be point out in insert SQL, so cols argument can't be empty")

        sql = self._insert_sql.format(
            cols=",".join([str(item) for item in cols]),
            table=table or self._table,
            values=",".join(["'"+str(cols[item])+"'" for item in cols])
        )
        if console:
            return sql
        else:
            return self.exec_sql(sql)

    def update(self, table=None, sets=None, where=None, order=None, limit=None, console=False):
        """
        更新数据
        :param table: 表名
        :param sets: 更新字段字典
        :param where: 更新条件
        :param order: 排序
        :param limit: 限制更新条数
        :param console: 是否输出SQL语句
        :return:
        """
        self._del_table(table)
        if not sets:
            raise SQLException("'SET' must be point out in update SQL, so sets argument can't be empty")
        sql = self._update_sql.format(
            table=table or self._table,
            sets=",".join([" SET "+item+"='"+str(sets[item])+"'" for item in sets]),
            where=self._del_where(where)
        )
        if order:
            sql += " ORDER BY " + self._del_order(order)
        if limit and isinstance(limit, int):
            sql += " LIMIT " + str(limit)
        if console:
            return sql
        else:
            return self.exec_sql(sql)

    def delete(self, table=None, where=None, order=None, limit=None, console=False):
        """
        删除数据
        :param table: 表名
        :param where: 条件
        :param order: 排序
        :param limit: 限制
        :param console: 是否打印SQL
        :return:
        """
        self._del_table(table)
        if not where:
            raise SQLException("you must point out where argument in delete SQL which at least should be 'True' or 1")
        sql = self._delete_sql.format(
            table=table or self._table,
            where=self._del_where(where)
        )
        if order:
            sql += " ORDER BY " + self._del_order(order)
        if limit and isinstance(limit, int):
            sql += " LIMIT " + str(limit)
        if console:
            return sql
        else:
            return self.exec_sql(sql)

    def insert_and_update(self, table=None, cols=None, console=False):
        '''
        存在数据时，更新数据
        不存在数据时，插入数据
        '''
        self._del_table(table)
        if not cols:
            raise SQLException("cols and values must be point out in insert SQL, so cols argument can't be empty")
        sql = self._insert_update_sql.format(
            cols=",".join([str(item) for item in cols]),
            table=table or self._table,
            values=",".join(["'" + str(cols[item]) + "'" for item in cols]),
            updates = ",".join([str(item)+"='"+str(cols[item])+"'" for item in cols])
        )
        if console:
            return sql
        else:
            return self.exec_sql(sql)


    def exec_sql(self, sql, console=False):
        """
        执行具体的SQL语句
        :param sql: 具体的SQL
        :param console: 是否console
        :return:
        """
        if console:
            return sql
        try:
            self._connect(*self._conn_args, **self._conn_kwargs)
            self._cursor.execute(sql)
            self._conn.commit()
        except Exception as e:
            if self._conn:
                self._conn.rollback()
            print e[1]
        else:
            self.rowcount = self._cursor.rowcount
            self.description = self._cursor.description
            return self._cursor.fetchall()

    def close(self):
        """
        关闭数据库连接
        """
        self._conn.close()

    def __del__(self):
        if self._conn:
            self._conn.close()

    def _desc(self,timeout):
        """
        获取表结构
        :param timeout: 过期时间，单位小时
        :return: 表结构dict
        """
        sql = "desc " + self._table
        structure = self.exec_sql(sql)
        sdict = {item['Field']: item for item in structure}

        sdict['timestamp'] = time.time()
        # 过期时间转化成秒
        sdict['overtime'] = timeout * 60 * 60
        with self._get_tmp_file('w') as f:
            json.dump(sdict, f)
        return sdict

    def desc(self, timeout=12, absupdate=False):
        """
        获得表结构
        :param timeout: 过期时间，默认12小时
        :param absupdate: 忽略过期时间，立即更新表结构
        :return:
        """
        if not self._table:
            raise SQLException("You havn't set table name ，you can set: self._table")
        try:
            if absupdate:
                raise Exception('')
            with self._get_tmp_file('r') as f:
                sdict = json.load(f)
            if sdict['timestamp']+sdict['overtime'] < time.time():
                raise Exception('')

        except Exception as e:
            sdict = self._desc(timeout)
        del sdict['timestamp']
        del sdict['overtime']
        return sdict

    def _get_tmp_file(self,mod):
        if not self._temp_dir:
            raise SQLException("The temporary dir isn't exist so that cann't save the table structure, you can set：self._tmp_dir=DIR")
        path_ = realpath( self._temp_dir+"/"+self._table)
        return open( path_, mod )

    def _set_cols(self):
        desc = self.desc()
        stru = {}
        for key in desc:
            stru[key] = {
                'field' : desc[key]['Field'],
                'default' : desc[key]['Default'],
                'key' : desc[key]['Key'],
                'null' : desc[key]['Null'],
                'type' : desc[key]['Type'],
            }
        return stru

    def set_cols(self,cols):
        """
        检查当前输入的cols，在表中是否存在
        该方法需要在子类中重写，但不强制
        :param cols: 列列表
        :return:
        """
        return True

    def trans(self):
        '事务操作'
        pass


class SQLException(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return repr(self.msg)

# if __name__ == "__main__":
#     print("This model cann't run in main namespace")