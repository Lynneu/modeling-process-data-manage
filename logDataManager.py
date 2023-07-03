import pandas as pd
import json
import re
import copy
import os
import subprocess
import csv
import time
import datetime
import itertools
from shutil import copyfile

skipList = ["*  StartedTransaction:  Initial Layout", "*  StartingFirstTransaction:  Initial Layout",
            "*  CommittingTransaction:  Initial Layout", "*  CommittingTransaction:  ExternalCopy",
            "*  CommittingTransaction:  input text", "*  StartedTransaction:  ",
            "*  CommittingTransaction:  Move", "*  CommittingTransaction:  start to edit text",
            "*  StartedTransaction:  TextEditing", "*  CommittingTransaction:  TextEditing",
            "*  CommittingTransaction:  LinkReshaping", "*  CommittedTransaction:  TextEditing",
            "*  StartingUndo:  Undo",
            "*  CommittingTransaction:  LinkShifting", "*  StartedTransaction:  LinkReshaping",
            "*  StartedTransaction:  Drop",
            "*  StartedTransaction:  Drag", '*  CommittedTransaction:  start to edit text',
            "*  CommittingTransaction:  Shifted Label", "*  StartedTransaction:  Shifted Label",
            "*  StartedTransaction:  Shifted Label", "*  StartingRedo:  Redo",
            "*  CommittingTransaction:  Resizing", "*  CommittingTransaction:  Delete",
            "*  StartedTransaction:  LinkShifting", "*  StartedTransaction:  Resizing",
            "*  CommittingTransaction:  Paste",
            "*  StartedTransaction:  Paste",
            "*  from SourceChanged:", "*  to SourceChanged:",
            "*  StartedTransaction:  Delete"
            ]


class datalog:
    def __init__(self, type, category, starttime, endtime, key=None, old=None, new=None, frompoint=None, topoint=None,
                 routes=[], text=None, detail=None):
        self.type = type
        self.category = category
        self.starttime = starttime
        self.endtime = endtime
        self.key = key
        self.old = old
        self.new = new
        self.routes = routes
        self.frompoint = frompoint
        self.topoint = topoint
        self.text = text
        self.detail = detail

    def __repr__(self):
        return repr("<datalog type:%s category:%s starttime:%s endtime:%s key:%s from:%s to:%s>" % (str(self.type), \
                                                                                                    str(self.category),
                                                                                                    str(self.starttime),
                                                                                                    str(self.endtime),
                                                                                                    str(self.key),
                                                                                                    str(self.frompoint),
                                                                                                    str(self.topoint)))


def cmp_time(a):
    return a["timeStamp"]


def duration(starttime, endtime):
    """计算操作持续时间"""
    return 0 if starttime > endtime else (endtime - starttime) / 1000

# 转换13位时间戳格式
def trans_date(time1, time2):
    dt_format = "%Y-%m-%d %H:%M:%S"
    dt1 = datetime.datetime.fromtimestamp(time1/1000)
    dt2 = datetime.datetime.fromtimestamp(time2/1000)
    return dt1.strftime(dt_format), dt2.strftime(dt_format)

def solve(List):
    # 新建一个空列表tmpList，用于存储连续的一组日志条目
    tmpList = []
    # 新建一个空列表datalogList，用于存储处理后的日志信息
    datalogList = []
    # 初始化映射表
    id_to_name_node = {}
    id_to_name_link = {}
    # 储存删除的元素，以便撤销恢复
    change_object = {}
    # 记录连续移动
    isContinuous_Move = 1
    # 记录连续resize
    isContinuous_Resize = 1
    # 记录连续LinkShifting
    isContinuous_LinkShifting = 1
    # 记录连续LinkReshaping
    isContinuous_LinkReshaping = 1
    # 遍历List中的每个日志条目
    for i in range(len(List)):
        change_object_len = len(change_object.keys())
        # 如果该条目的content字段开头为"!"，将其添加到tmpList列表中
        if (List[i]['content'][0] == '!'):
            tmpList.append(List[i])
        else:
            # print(List[i]['content'])
            # 如果tmpList列表为空，且当前日志条目不属于特定的组合模式，则跳过该条目
            if len(tmpList) == 0 and List[i]['content'] != "*  CommittedTransaction:  Initial Layout" and \
                    List[i]['content'] != "*  FinishedUndo:  Undo" and \
                    List[i]['content'] != "*  FinishedRedo:  Redo" and \
                    List[i]['content'] != "*  CommittedTransaction:  Move" and \
                    List[i]['content'] != "*  CommittedTransaction:  Resizing" and \
                    List[i]['content'] != "*  CommittedTransaction:  LinkReshaping" and \
                    List[i]['content'] != "*  CommittedTransaction:  LinkShifting":
                    # List[i]['content'] != "*  StartedTransaction:  Shifted Label" and \
                continue
            # 添加节点
            if re.match(r"\*  CommittedTransaction:  ExternalCopy", List[i]['content']):
                # 在tmpList中找到最后一条包含category和key信息的日志条目
                for j in range(len(tmpList) - 1, -1, -1):
                    # print(j)
                    if "category:" in tmpList[j]['content'] and "key:" in tmpList[j]['content']:
                        lastpoint = j
                        break
                # 在tmpList中找到第一条包含category和key信息的日志条目
                for j in range(len(tmpList)):
                    if "category:" in tmpList[j]['content'] and "key:" in tmpList[j]['content']:
                        firstpoint = j
                        break
                # 提取旧值和新值
                # 将日志中最后一个符合条件的条目的内容字符串content按照空格进行分割，返回一个字符串列表
                newlogList = re.split(r"[ ]+", tmpList[lastpoint]['content'])
                # 将日志中第一个条目的内容字符串content按照空格进行分割，返回一个字符串列表
                oldlogList = re.split(r"[ ]+", tmpList[firstpoint]['content'])
                # 在 newlogList 中查找字符串 "new:" 所在的位置索引
                newindex = newlogList.index("new:")
                # 获取 newlogList 中 "new:" 后面的第一个元素，即新节点的 x 坐标
                newx = newlogList[newindex + 1]
                # 获取 newlogList 中 "new:" 后面的第二个元素，即新节点的 y 坐标
                newy = newlogList[newindex + 2]
                # 在 oldlogList 中查找字符串 "old:" 所在的位置索引
                oldindex = oldlogList.index("old:")
                # 获取 oldlogList 中 "old:" 后面的第一个元素，即旧节点的 x 坐标
                oldx = oldlogList[oldindex + 1]
                # 获取 oldlogList 中 "old:" 后面的第二个元素，即旧节点的 y 坐标
                oldy = oldlogList[oldindex + 2]
                # 获取日志中最后一个符合条件的条目的内容字符串 content
                log = tmpList[lastpoint]['content']
                # 将 log 按照空格进行分割，返回一个字符串列表
                logList = re.split(r"[ ]+", log)
                # 在 logList 中查找字符串 "category:" 所在的位置索引
                categoryindex = logList.index("category:")
                # 获取 logList 中 "category:" 后面的元素，即该操作所在的分类
                category = logList[categoryindex + 1]
                # 该操作的开始时间
                starttime = tmpList[0]['timeStamp']
                # 该操作的结束时间
                endtime = tmpList[-1]['timeStamp']
                # 在 logList 中查找字符串 "key:" 所在的位置索引
                keyindex = logList.index("key:")
                key = logList[keyindex + 1]
                # 操作对象的文本内容
                try:
                    textindex = logList.index("text:")
                    text = logList[textindex + 1]
                except:
                    text = ""
                # print(text)
                # print(key)
                # 找到元素名字的id
                namepoint = None
                for j in range(len(tmpList)):
                    if "!mChangedEvent.Insert nodeDataArray" in tmpList[j]['content']:
                        namepoint = j
                        break
                if namepoint:
                    log = tmpList[namepoint]['content']
                    logList = re.split(r"[ ]+", log)
                    name_id = logList[-1]
                    nameindex = logList.index("new:")
                    name = logList[nameindex + 1]
                    # print("addnodename: " + name)
                    # print("key:" + key)
                    # print(tmpList)
                    if key not in id_to_name_node:
                        # 创建元素，写入映射表
                        id_to_name_node[key] = {'name': name, 'name_id': name_id, 'category': category}
                        # print(id_to_name_node)
                        # 创建一个名为 "datalog" 的对象，包含有用的信息，然后将其添加到 "datalogList" 列表中
                        datalogList.append(
                            datalog("AddingNode", category, starttime, endtime, old=(oldx, oldy), new=(newx, newy),
                                    key=key, routes=copy.deepcopy(tmpList), text=text))
            # 编辑文本内容
            elif re.match(r"\*  CommittedTransaction:  input text", List[i]['content']):
                for j in range(len(tmpList)):
                    # print(j)
                    if "!m text:" in tmpList[j]['content']:
                        logpoint = j
                        break
                log = tmpList[logpoint]['content']
                logList = re.split(r"[ ]+", log)
                oldindex = logList.index("old:")
                newindex = logList.index("new:")
                # 取出节点原本的文本内容
                oldtext = logList[oldindex + 1]
                starttime = tmpList[0]['timeStamp']
                endtime = tmpList[-1]['timeStamp']
                # 如果原本没有文本内容，则令其为空
                if oldtext == "new:":
                    oldtext = ""
                # 取出节点新的文本内容
                newtext = logList[newindex + 1]
                # 如果节点没有新的文本内容，则令其为空
                if newtext == "category:" or newtext == "from:":
                    newtext = ""
                # 取出修改后的元素name
                nameindex = logList.index("text:")
                name = logList[nameindex + 1]
                if name == '[object':
                    name = ''
                # 如果存在category和key信息
                if "key:" in log and "category:" in log:
                    categoryindex = logList.index("category:")
                    category = logList[categoryindex + 1]
                    keyindex = logList.index("key:")
                    key = logList[keyindex + 1]
                    # 修改映射表中key对应元素的name
                    if key not in id_to_name_node:
                        id_to_name_node[key] = {'name': name, 'name_id': None, 'category': category}
                    else:
                        id_to_name_node[key]['name'] = name
                    datalogList.append(datalog("TextEditing", category, starttime, endtime,
                                               key=key, old=oldtext, new=newtext, text=newtext))
                # 如果不存在category和key信息，说明是数据流的文本内容
                else:
                    category = "dataflow"
                    fromindex = logList.index("from:")
                    frompoint = logList[fromindex + 1]
                    toindex = logList.index("to:")
                    topoint = logList[toindex + 1]
                    # key = "from " + frompoint + " to " + topoint
                    # 修改映射表中key对应元素的name
                    # print("id_to_name_link")
                    # print(id_to_name_link)
                    # if key not in id_to_name_link:
                    #     id_to_name_link[key] = {'name': name, 'name_id': None, 'category': 'dataflow',
                    #                             'frompoint': frompoint, 'topoint': topoint}
                    # else:
                    #     id_to_name_link[key]['name'] = name
                    # 检查字典里连接这两个元素的数据流是否不止一条
                    testkey = "from " + frompoint + " to " + topoint
                    isMore = 0
                    for k in id_to_name_link.keys():
                        if testkey in k:
                            if 'number:' in k:
                                isMore = 1
                                break
                    if isMore == 0:
                        key = next((k for k, v in id_to_name_link.items() if
                                (v.get('frompoint') == frompoint and v.get('topoint') == topoint)), None)
                    else:
                        key = next((k for k, v in id_to_name_link.items() if
                                (v.get('frompoint') == frompoint and v.get('topoint') == topoint and v.get('name') in oldtext)), None)
                    if key is not None:
                        id_to_name_link[key]['name'] = name
                    else:
                        key = testkey
                        id_to_name_link[key] = {'name': name, 'name_id': None, 'category': category,
                                                'frompoint': frompoint, 'topoint': topoint,
                                                'isBothway': False, 'isReverse': False}

                    datalogList.append(datalog("TextEditing", category, starttime, endtime, key=key,
                                               frompoint=frompoint, topoint=topoint, old=oldtext, new=newtext,
                                               text=newtext))
            # 添加数据流
            elif re.match(r"(\*  CommittedTransaction:  Linking)|(\*  CommittingTransaction:  Linking)",
                          List[i]['content']):
                # print(tmpList)
                # 类型为数据流
                category = "dataflow"
                starttime = tmpList[0]['timeStamp']
                endtime = tmpList[-1]['timeStamp']
                tar = 0
                # 查找from所在的位置
                for index in range(len(tmpList)):
                    if "from:" in tmpList[index]['content']:
                        tar = index
                        break
                logList = re.split(r"[ ]+", tmpList[tar]['content'])
                # 获取from的值
                try:
                    fromindex = logList.index("from:")
                    frompoint = logList[fromindex + 1]
                except:
                    print(tmpList)
                # 获取to的值
                toindex = logList.index("to:")
                topoint = logList[toindex + 1]
                # 获取操作对象的文本内容
                try:
                    textindex = logList.index("text:")
                    text = logList[textindex + 1]
                except:
                    text = ""
                # print(text)
                key = "from " + frompoint + " to " + topoint

                # 找到元素名字的id
                for j in range(len(tmpList)):
                    if "!mChangedEvent.Insert linkDataArray" in tmpList[j]['content']:
                        namepoint = j
                        break
                log = tmpList[namepoint]['content']
                logList = re.split(r"[ ]+", log)
                name_id = logList[-1]
                nameindex = logList.index("new:")
                name = logList[nameindex + 1]
                if (key not in id_to_name_link):
                    # 创建元素，写入映射表
                    id_to_name_link[key] = {'name': name, 'name_id': name_id, 'category': category,
                                            'frompoint': frompoint, 'topoint': topoint,
                                            'isBothway': False, 'isReverse': False}
                    datalogList.append(datalog("AddingLink", category, starttime, endtime, key=key,
                                               frompoint=frompoint, topoint=topoint, text=text))
                else:
                    # 如果已经存在连接同样两个元素的数据流
                    found = False
                    datatflow_num = 0
                    for k in id_to_name_link.keys():
                        if key in k:
                            # 如果已经存在相同的name_id,说明该条数据流已存在，不再重复添加
                            if id_to_name_link[k]['name_id'] == name_id:
                                found = True
                                break
                    if not found:
                        for k in id_to_name_link.keys():
                            if key in k and 'number:' in k:
                                numberindext = k.split().index('number:')
                                value = int(k.split()[numberindext + 1])
                                datatflow_num = max(datatflow_num, value)
                                # print('addflow!!!!!')
                                # print(k)
                        datatflow_num = datatflow_num + 1
                        key = key + '\nnumber: ' + str(datatflow_num)
                        id_to_name_link[key] = {'name': name, 'name_id': name_id, 'category': category,
                                                'frompoint': frompoint, 'topoint': topoint,
                                                'isBothway': False, 'isReverse': False}
                        # print(id_to_name_link)
                        # print('addflow over!!')
                        datalogList.append(datalog("AddingLink", category, starttime, endtime, key=key,
                                                   frompoint=frompoint, topoint=topoint, text=text))


            # 移动节点
            elif re.match(r"\*  CommittedTransaction:  Move", List[i]['content']):
                # print(tmpList)
                # 处理连续移动多次信息
                if len(tmpList) == 0:
                    if datalogList[-1].type == 'MovingNode':
                        time_interval1 = duration(datalogList[-1].endtime, List[i]['timeStamp'])
                        time_interval2 = duration(List[i - 1]['timeStamp'], List[i]['timeStamp'])
                        if time_interval1 != 0 and time_interval2 != 0:
                            # print(datalogList[-1].endtime)
                            # print(List[i]['timeStamp'])
                            # print(time_interval)
                            isContinuous_Move = isContinuous_Move + 1
                        if ((i == len(List) - 1) or (List[i + 1]['content'] != "*  CommittedTransaction:  Move")) and isContinuous_Move != 1:
                            datalogList[-1].detail = '连续移动多次:' + str(isContinuous_Move)
                            isContinuous_Move = 1
                           # print(datalogList[-1].key + ' ' + datalogList[-1].detail)
                else:
                    # 记录已经处理过的移动节点
                    keylist = []
                    for j in range(len(tmpList)):
                        if "category:" in tmpList[j]['content'] and "key:" in tmpList[j]['content']:
                            lastpoint = j
                            log = tmpList[lastpoint]['content']
                            logList = re.split(r"[ ]+", log)
                            keyindex = logList.index("key:")
                            key = logList[keyindex + 1]
                            if key in keylist:
                                continue
                            else:
                                keylist.append(key)
                                try:
                                    categoryindex = logList.index("category:")
                                    category = logList[categoryindex + 1]
                                    textindex = logList.index("text:")
                                    text = logList[textindex + 1]
                                except:
                                    category = "?"
                                    key = text = None
                                starttime = tmpList[0]['timeStamp']
                                endtime = List[i]['timeStamp']
                                datalogList.append(
                                    datalog("MovingNode", category, starttime, endtime,
                                            key=key, routes=copy.deepcopy(tmpList), text=text))

                                # 处理节点文本编辑过程缺失
                                for i in range(len(datalogList) - 1, -1, -1):
                                    # 如果先找到的是删除信息，说明该元素是删除后新添加的，还未被修改过text
                                    if datalogList[i].type == 'Delete' and \
                                            datalogList[i].category != 'dataflow' and \
                                            datalogList[i].key == key:
                                        break
                                    if datalogList[i].type == 'TextEditing' and \
                                            datalogList[i].category != 'dataflow' and \
                                            datalogList[i].key == key:
                                        if datalogList[i].text != datalogList[-1].text:
                                            print('complete node word!')
                                            print(datalogList[i].text)
                                            datalogList[i].text = datalogList[-1].text
                                            if key in id_to_name_node:
                                                id_to_name_node[key]['name'] = datalogList[-1].text
                                            print(datalogList[-1].text)
                                            print(id_to_name_node)
                                            print('---end complete---')
                                        break

                                # 处理数据流文本编辑过程缺失
                                link_textlist = []
                                for j in range(len(tmpList)):
                                    if "from:" in tmpList[j]['content']:
                                        log = tmpList[j]['content']
                                        logList = re.split(r"[ ]+", log)
                                        fromindex = logList.index("from:")
                                        frompoint = logList[fromindex + 1]
                                        toindex = logList.index("to:")
                                        topoint = logList[toindex + 1]
                                        key = "from " + frompoint + " to " + topoint
                                        # 获取操作对象的文本内容
                                        textindex = logList.index("text:")
                                        text = logList[textindex + 1]
                                        hasKey = 0
                                        for tpl in link_textlist:
                                            if key in tpl:
                                                hasKey = 1
                                                break
                                        if hasKey == 0:
                                            new_entry = (key, text)
                                            link_textlist.append(new_entry)
                                print('link_textlist')
                                print(link_textlist)
                                for i in range(len(link_textlist)):
                                    key = link_textlist[i][0]
                                    text = link_textlist[i][1]
                                    for j in range(len(datalogList) - 1, -1, -1):
                                        # 如果先找到的是删除信息，说明该元素是删除后新添加的，还未被修改过text
                                        if datalogList[j].type == 'Delete' and \
                                                datalogList[j].category == 'dataflow' and \
                                                datalogList[j].key == key:
                                            print('跳过啦！！！！！')
                                            break
                                        if datalogList[j].type == 'TextEditing' and \
                                                datalogList[j].category == 'dataflow' and \
                                                datalogList[j].key == key:
                                            if datalogList[j].text != text:
                                                print('complete link word!')
                                                print(datalogList[j].text)
                                                print(text)
                                                datalogList[j].text = text
                                                if key in id_to_name_link:
                                                    id_to_name_link[key]['name'] = text
                                                print(id_to_name_link)
                                                print('----end comletelink---')
                                            break


            # 移动数据流
            elif re.match(r"\*  CommittedTransaction:  LinkShifting", List[i]['content']):
                # 处理连续调整多次信息
                if len(tmpList) == 0:
                    if datalogList[-1].type == 'LinkShifting':
                        time_interval1 = duration(datalogList[-1].endtime, List[i]['timeStamp'])
                        time_interval2 = duration(List[i - 1]['timeStamp'], List[i]['timeStamp'])
                        if time_interval1 != 0 and time_interval2 != 0:
                            # print(datalogList[-1].endtime)
                            # print(List[i]['timeStamp'])
                            # print(time_interval)
                            isContinuous_LinkShifting = isContinuous_LinkShifting + 1
                        if (i == len(List) - 1) or (
                                List[i + 1]['content'] != "*  CommittedTransaction:  LinkShifting" and isContinuous_LinkShifting != 1):
                            datalogList[-1].detail = '连续移动多次:' + str(isContinuous_LinkShifting)
                            isContinuous_LinkShifting = 1
                            # print(datalogList[-1].key + ' ' + datalogList[-1].detail)
                else:
                    # print(tmpList)
                    for j in range(len(tmpList)):
                        if "from:" in tmpList[j]['content']:
                            firstpoint = j
                            break
                    log = tmpList[firstpoint]['content']
                    lastlogList = re.split(r"[ ]+", tmpList[-1]['content'])
                    logList = re.split(r"[ ]+", log)
                    # print(logList)
                    oldindex = logList.index("old:")
                    newindex = lastlogList.index("new:")
                    textindex = lastlogList.index("text:")
                    if len(lastlogList) == textindex + 1:
                        text = ""
                    else:
                        text = lastlogList[textindex + 1]
                    old = logList[oldindex + 1]
                    new = lastlogList[newindex + 1]
                    starttime = tmpList[0]['timeStamp']
                    endtime = tmpList[-1]['timeStamp']
                    fromindex = logList.index("from:")
                    frompoint = logList[fromindex + 1]
                    toindex = logList.index("to:")
                    topoint = logList[toindex + 1]
                    key = next((k for k, v in id_to_name_link.items() if
                                (v.get('frompoint') == frompoint and v.get('topoint') == topoint and v.get('name') == text)), None)
                    # key = "from " + frompoint + " to " + topoint
                    datalogList.append(datalog("LinkShifting", "dataflow", starttime, endtime, key=key, old=old, new=new,
                                               frompoint=frompoint, topoint=topoint, routes=copy.deepcopy(tmpList),
                                               text=text))
                # 处理文本编辑过程缺失
                for i in range(len(datalogList) - 1, -1 , -1):
                    # 如果先找到的是删除信息，说明该元素是删除后新添加的，还未被修改过text
                    if datalogList[i].type == 'Delete' and \
                            datalogList[i].category == 'dataflow' and \
                            datalogList[i].key == key:
                        break
                    if datalogList[i].type == 'TextEditing' and \
                        datalogList[i].category == 'dataflow' and \
                        datalogList[i].key == key:
                        if datalogList[i].text != datalogList[-1].text:
                            datalogList[i].text = datalogList[-1].text
                            if key in id_to_name_link:
                                id_to_name_link[key]['name'] = datalogList[-1].text
                        break

                # print(tmpList)
            # 改变数据流形状
            elif re.match(r"\*  CommittedTransaction:  LinkReshaping", List[i]['content']):
                # 处理连续调整多次信息
                if len(tmpList) == 0:
                    if datalogList[-1].type == 'LinkReshaping':
                        time_interval1 = duration(datalogList[-1].endtime, List[i]['timeStamp'])
                        time_interval2 = duration(List[i - 1]['timeStamp'], List[i]['timeStamp'])
                        if time_interval1 != 0 and time_interval2 != 0:
                            # print(datalogList[-1].endtime)
                            # print(List[i]['timeStamp'])
                            # print(time_interval)
                            isContinuous_LinkReshaping = isContinuous_LinkReshaping + 1
                        if (i == len(List) - 1) or (
                                List[i + 1][
                                    'content'] != "*  CommittedTransaction:  LinkReshaping" and isContinuous_LinkReshaping != 1):
                            datalogList[-1].detail = '连续移动多次:' + str(isContinuous_LinkReshaping)
                            isContinuous_LinkReshaping = 1
                            # print(datalogList[-1].key + ' ' + datalogList[-1].detail)
                else:
                    # print(tmpList)
                    if "from:" not in tmpList[0]['content']:
                        log = tmpList[1]['content']
                    else:
                        log = tmpList[0]['content']
                    lastlogList = re.split(r"[ ]+", tmpList[-1]['content'])
                    logList = re.split(r"[ ]+", log)
                    oldindex = logList.index("old:")
                    newindex = lastlogList.index("new:")
                    textindex = lastlogList.index("text:")
                    text = lastlogList[textindex + 1]
                    old = logList[oldindex + 1]
                    new = lastlogList[newindex + 1]
                    starttime = tmpList[0]['timeStamp']
                    endtime = tmpList[-1]['timeStamp']
                    fromindex = logList.index("from:")
                    frompoint = logList[fromindex + 1]
                    toindex = logList.index("to:")
                    topoint = logList[toindex + 1]
                    key = next((k for k, v in id_to_name_link.items() if
                                (v.get('frompoint') == frompoint and v.get('topoint') == topoint and v.get('name') == text)), None)
                    # key = "from " + frompoint + " to " + topoint
                    datalogList.append(datalog("LinkReshaping", "dataflow", starttime, endtime, key=key, old=old, new=new,
                                               frompoint=frompoint, topoint=topoint, routes=copy.deepcopy(tmpList),
                                               text=text))
            # 初始化布局
            elif re.match(r"\*  CommittedTransaction:  Initial Layout", List[i]['content']):
                starttime = List[i]['timeStamp']
                endtime = List[i]['timeStamp']
                datalogList.append(datalog("Init", None, starttime, endtime))
            # 重做
            elif re.match(r"\*  FinishedRedo:  Redo", List[i]['content']):
                redolength = 0
                # 处理多次恢复
                if datalogList[-1].type == 'Redo':
                    for i in range(len(datalogList) - 1, -1, -1):
                        if (datalogList[i].type == 'Redo'):
                            redolength = redolength + 1
                        else:
                            break
                i = len(datalogList) - 1 - redolength
                logList = datalogList[i].detail.split()
                numindex = logList.index('撤销元素个数:')
                num = logList[numindex + 1]
                keyindex = logList.index('key:')
                key = logList[keyindex + 1]
                categoryindex = logList.index('category:')
                category = logList[categoryindex + 1]
                textindex = logList.index('text:')
                text = logList[textindex + 1]
                typeindex = logList.index('撤销动作:')
                type = logList[typeindex + 1].split("_")[0]

                if type == 'AddingNode' or type == 'PastingNode':
                    elements = datalogList[i].detail.strip().split("\n\n")  # 使用两个换行符分割元素，并去除开头和结尾的空白字符
                    values = []
                    target_string = "撤销元素个数:"
                    numindex = datalogList[i].detail.index(target_string) + len(target_string) - 1
                    num = int(elements[0][numindex + 1])
                    # print(elements[0])
                    # print(numindex)
                    # print(num)
                    for element in elements:
                        lines = element.strip().split("\n")  # 分割每个元素的行，并去除开头和结尾的空白字符
                        for line in lines[num + 1:]:  # 跳过前两行（撤销动作和撤销元素个数）
                            if ":" in line:
                                info = {}  # 创建一个新的字典用于存储键值对
                                key_value_pairs = line.split()  # 分割键值对
                                for key_value_pair in key_value_pairs:
                                    key, value = key_value_pair.split(":", 1)  # 分割键和值
                                    info[key.strip()] = value.strip()  # 去除空格并存储键值对
                                values.append(info)
                    # 提取了撤销操作的每一个元素信息后开始恢复或删除这些元素，可以把提取元素信息放到循环最外面，然后再根据撤销的操作类型进行处理

                starttime = List[i]['timeStamp']
                endtime = List[i]['timeStamp']



                datalogList.append(datalog("Redo", None, starttime, endtime))
            # 撤销
            elif re.match(r"\*  FinishedUndo:  Undo", List[i]['content']):
                # 处理撤销信息重复记录
                time_interval = duration(List[i - 1]['timeStamp'], List[i]['timeStamp'])
                if (datalogList[-1].type != 'Undo') or \
                        (datalogList[-1].type == 'Undo' and time_interval != 0):
                    # 处理连续撤销
                    undolength = 1
                    for i in range(len(datalogList) - 1, -1, -1):
                        if(datalogList[i].type == 'Undo'):
                            try:
                                logList = datalogList[i].detail.split()
                                numindex = logList.index('撤销元素个数:')
                                num = logList[numindex + 1]
                                undolength = undolength + num + 1
                            except:
                                undolength = undolength + 2
                        else:
                            break
                    starttime = List[i]['timeStamp']
                    endtime = List[i]['timeStamp']
                    # 存放同时删除或同时添加的元素
                    lastGroup = []
                    lastGroup.append(datalogList[-1 * undolength])
                    # 将操作时间间隔为0的都算作一组操作
                    for i in range(len(datalogList) - undolength - 1, -1, -1):
                        time_interval = duration(datalogList[i].endtime, lastGroup[-1].starttime)
                        if time_interval == 0:
                            lastGroup.append(datalogList[i])
                            # print(datalogList[i].starttime)
                            # print(lastGroup[-1].endtime)
                            # print(lastGroup)
                        else:
                            break
                    numofItem = 0
                    detailofItem = ''
                    detailofType = '撤销动作: '
                    type = datalogList[-1 * undolength].type
                    # print("撤销动作")
                    # print(type)
                    # print(-1 * undolength)
                    newundolength = -1 * undolength
                    print(datalogList[newundolength])
                    # 如果撤销的操作是删除，相当于添加元素
                    if type == 'Delete':
                        for i in range(len(lastGroup)):
                            key = lastGroup[i].key
                            category = lastGroup[i].category
                            text = lastGroup[i].text
                            # 存入删除的一组元素的信息
                            newdetail = "key: " + key + " category: " + category + " text: " + text
                            detailofItem = detailofItem + '\n' + newdetail
                            detailofType = detailofType + type + "_" + category + '\n'
                            numofItem = numofItem + 1
                            if lastGroup[i].category == 'dataflow':
                                if key in change_object:
                                    id_to_name_link[key] = change_object[key]
                                    del change_object[key]
                                    print('undo delete link!')
                                    print(id_to_name_link)
                                    print(key)
                                    print(id_to_name_link[key])
                                    print('------end to undo-----')
                            else:
                                if key in change_object:
                                    id_to_name_node[key] = change_object[key]
                                    del change_object[key]
                                    print('undo delete node!')
                                    print(id_to_name_node)
                                    print('------end to undo-----')
                    # 如果撤销的操作是添加元素，相当于删除元素
                    elif type == 'AddingNode' or type == 'PastingNode':
                        for i in range(len(lastGroup)):
                            key = lastGroup[i].key
                            category = lastGroup[i].category
                            text = lastGroup[i].text
                            # 存入添加的一组元素的信息
                            newdetail = "key: " + key + " category: " + category + " text: " + text
                            detailofItem = detailofItem + '\n' + newdetail
                            detailofType = detailofType + type + "_" + category + '\n'
                            numofItem = numofItem + 1
                            if key in change_object:
                                change_object[key] = id_to_name_node[key]
                                del id_to_name_node[key]
                    # 如果撤销的操作是添加数据流，相当于删除数据流
                    elif type == 'AddingLink' or type == 'PastingLink':
                        for i in range(len(lastGroup)):
                            key = lastGroup[i].key
                            category = lastGroup[i].category
                            text = lastGroup[i].text
                            # 存入删除的一组数据流的信息
                            newdetail = "key: " + key + " category: " + category + " text: " + text
                            detailofItem = detailofItem + '\n' + newdetail
                            detailofType = detailofType + type + "_" + category + '\n'
                            numofItem = numofItem + 1
                            if key in change_object:
                                change_object[key] = id_to_name_link[key]
                                del id_to_name_link[key]
                    # 如果撤销的是文本编辑
                    elif type == 'TextEditing':
                        numofItem = 1
                        text = datalogList[-1 * undolength].text
                        oldtext = datalogList[-1 * undolength].old
                        category = datalogList[-1 * undolength].category
                        key = datalogList[-1 * undolength].key
                        print("undonum: " + str(undolength))
                        print("text: " + text)
                        print("oldtext:" + oldtext)
                        if category == 'dataflow':
                            id_to_name_link[key]['name'] = oldtext
                        else:
                            id_to_name_node[key]['name'] = oldtext
                        detailofItem = "\n" + "key: " + key + " category: " + category + " text: " + oldtext
                        detailofType = detailofType + type + "_" + category + '\n'
                    # 如果撤销的是箭头更改
                    elif type == 'ChangeFromArrow':
                        numofItem = 1
                        key = datalogList[-1 * undolength].key
                        text = datalogList[-1 * undolength].text
                        category = datalogList[-1 * undolength].category
                        key = datalogList[-1 * undolength].key
                        isBothway = isReverse = None
                        isBothway = id_to_name_link[key]['isBothway']
                        isReverse = id_to_name_link[key]['isReverse']
                        isBothway = ~isBothway
                        isReverse = ~isReverse
                        id_to_name_link[key]['isBothway'] = isBothway
                        id_to_name_link[key]['isReverse'] = isReverse
                        detailofItem = "\n" + "key: " + key + " category: " + category + " text: " + text
                        detailofType = detailofType + type + "_" + category + '\n'

                    elif type == 'ChangeToArrow':
                        numofItem = 1
                        key = datalogList[-1 * undolength].key
                        text = datalogList[-1 * undolength].text
                        category = datalogList[-1 * undolength].category
                        key = datalogList[-1 * undolength].key
                        isBothway = isReverse = None
                        isBothway = id_to_name_link[key]['isBothway']
                        isReverse = id_to_name_link[key]['isReverse']
                        isBothway = ~isBothway
                        id_to_name_link[key]['isBothway'] = isBothway
                        detailofItem = "\n" + "key: " + key + " category: " + category + " text: " + text
                        detailofType = detailofType + type + "_" + category + '\n'

                    else:
                        numofItem = 1
                        text = datalogList[-1 * undolength].text
                        category = datalogList[-1 * undolength].category
                        key = datalogList[-1 * undolength].key
                        if text is None:
                            text = ''
                        if category is None:
                            category = ''
                        if key is None:
                            key = ''
                        detailofItem = "\n" + "key: " + key + " category: " + category + " text: " + text
                        detailofType = detailofType + type + "_" + category + '\n'

                    detail = detailofType + "撤销元素个数: " + str(numofItem) + detailofItem


                    datalogList.append(datalog("Undo", None, starttime, endtime, detail=detail))
            # 改变节点大小
            elif re.match(r"\*  CommittedTransaction:  Resizing", List[i]['content']):
                # print(tmpList)
                # 处理连续调整多次信息
                if len(tmpList) == 0:
                    if datalogList[-1].type == 'Resizing':
                        time_interval1 = duration(datalogList[-1].endtime, List[i]['timeStamp'])
                        time_interval2 = duration(List[i - 1]['timeStamp'], List[i]['timeStamp'])
                        if time_interval1 != 0 and time_interval2 != 0:
                            # print(datalogList[-1].endtime)
                            # print(List[i]['timeStamp'])
                            # print(time_interval)
                            isContinuous_Resize = isContinuous_Resize + 1
                        if (i == len(List) - 1) or (
                                List[i + 1]['content'] != "*  CommittedTransaction:  Resizing" and isContinuous_Resize != 1):
                            datalogList[-1].detail = '连续调整多次:' + str(isContinuous_Resize)
                            isContinuous_Resize = 1
                            # print(datalogList[-1].key + ' ' + datalogList[-1].detail)
                else:
                    # 在tmpList中找到最后一条包含category和key信息的日志条目
                    firstpoint = lastpoint = None
                    for j in range(len(tmpList) - 1, -1, -1):
                        if "category:" in tmpList[j]['content'] and "key:" in tmpList[j]['content']:
                            lastpoint = j
                            break
                    # 在tmpList中找到第一条包含category和key信息的日志条目
                    for j in range(len(tmpList)):
                        if "category:" in tmpList[j]['content'] and "key:" in tmpList[j]['content']:
                            firstpoint = j
                            break
                    if lastpoint is not None and firstpoint is not None:
                        newlogList = re.split(r"[ ]+", tmpList[lastpoint]['content'])
                        oldlogList = re.split(r"[ ]+", tmpList[firstpoint]['content'])
                        # 取出新的x，y坐标
                        newindex = newlogList.index("new:")
                        newx = newlogList[newindex + 1]
                        newy = newlogList[newindex + 2]
                        # 取出旧的x，y坐标
                        oldindex = oldlogList.index("old:")
                        oldx = oldlogList[oldindex + 1]
                        # 判断是否存在旧的x，y坐标
                        if oldx != "undefined":
                            oldy = oldlogList[oldindex + 2]
                        else:
                            oldy = "undefined"
                        log = tmpList[lastpoint]['content']
                        # print(tmpList)
                        # print(log)
                        logList = re.split(r"[ ]+", log)
                        categoryindex = logList.index("category:")
                        category = logList[categoryindex + 1]
                        # 操作开始时间和结束时间
                        starttime = tmpList[0]['timeStamp']
                        endtime = tmpList[-1]['timeStamp']
                        keyindex = logList.index("key:")
                        key = logList[keyindex + 1]
                        # 获取操作对象的文本内容
                        try:
                            textindex = newlogList.index("text:")
                            text = newlogList[textindex + 1]
                        except:
                            text = ""
                        # print(text)
                        datalogList.append(datalog("Resizing", category, starttime, endtime, old=(oldx, oldy), new=(newx, newy),
                                                   key=key, routes=copy.deepcopy(tmpList), text=text))

                        # 处理节点文本编辑过程缺失
                        for i in range(len(datalogList) - 1, -1, -1):
                            # 如果先找到的是删除信息，说明该元素是删除后新添加的，还未被修改过text
                            if datalogList[i].type == 'Delete' and \
                                    datalogList[i].category != 'dataflow' and \
                                    datalogList[i].key == key:
                                break
                            if datalogList[i].type == 'TextEditing' and \
                                    datalogList[i].category != 'dataflow' and \
                                    datalogList[i].key == key:
                                if datalogList[i].text != datalogList[-1].text:
                                    print('complete node word!')
                                    print(datalogList[i].text)
                                    datalogList[i].text = datalogList[-1].text
                                    if key in id_to_name_node:
                                        id_to_name_node[key]['name'] = datalogList[-1].text
                                    print(datalogList[-1].text)
                                    print(id_to_name_node)
                                    print('---end complete---')
                                break

                        # 处理数据流文本编辑过程缺失
                        # 可能不止一条数据流
                        link_textlist = []
                        for j in range(len(tmpList)):
                            if "from:" in tmpList[j]['content']:
                                log = tmpList[j]['content']
                                logList = re.split(r"[ ]+", log)
                                fromindex = logList.index("from:")
                                frompoint = logList[fromindex + 1]
                                toindex = logList.index("to:")
                                topoint = logList[toindex + 1]
                                key = "from " + frompoint + " to " + topoint
                                # 获取操作对象的文本内容
                                textindex = logList.index("text:")
                                text = logList[textindex + 1]
                                hasKey = 0
                                for tpl in link_textlist:
                                    if key in tpl:
                                        hasKey = 1
                                        break
                                if hasKey == 0:
                                    new_entry = (key, text)
                                    link_textlist.append(new_entry)
                        print('link_textlist')
                        print(link_textlist)
                        for i in range(len(link_textlist)):
                            key = link_textlist[i][0]
                            text = link_textlist[i][1]
                            for j in range(len(datalogList) - 1, -1, -1):
                                # 如果先找到的是删除信息，说明该元素是删除后新添加的，还未被修改过text
                                if datalogList[j].type == 'Delete' and \
                                        datalogList[j].category == 'dataflow' and \
                                        datalogList[j].key == key:
                                    break
                                if datalogList[j].type == 'TextEditing' and \
                                        datalogList[j].category == 'dataflow' and \
                                        datalogList[j].key == key:
                                    if datalogList[j].text != text:
                                        print('complete link word!')
                                        print(datalogList[j].text)
                                        print(text)
                                        datalogList[j].text = text
                                        if key in id_to_name_link:
                                            id_to_name_link[key]['name'] = text
                                        print(id_to_name_link)
                                        print('----end comletelink---')
                                    break

            # 移动文本标签
            elif re.match(r"\*  CommittedTransaction:  Shifted Label", List[i]["content"]):
                # print(tmpList)

                if "from:" in tmpList[0]['content']:
                    oldlogList = re.split(r"[ ]+", tmpList[0]['content'])
                else:
                    try:
                        oldlogList = re.split(r"[ ]+", tmpList[1]['content'])
                    except:
                        oldlogList = re.split(r"[ ]+", tmpList[0]['content'])
                try:
                    newlogList = re.split(r"[ ]+", tmpList[-1]['content'])
                    newindex = newlogList.index("new:")
                    newx = newlogList[newindex + 1]
                    newy = newlogList[newindex + 2]
                    oldindex = oldlogList.index("old:")
                    oldx = oldlogList[oldindex + 1]
                    oldy = oldlogList[oldindex + 2]
                except:
                    oldx = None
                    oldy = None
                    newx = None
                    newy = None
                starttime = tmpList[0]['timeStamp']
                endtime = tmpList[-1]['timeStamp']
                tar = 0
                # 找到第一个含有from信息的日志条目
                for index in range(len(tmpList)):
                    if "from:" in tmpList[index]['content']:
                        tar = index
                        break
                logList = re.split(r"[ ]+", tmpList[tar]['content'])
                textindex = logList.index("text:")
                text = logList[textindex + 1]
                # 提取from和to信息
                try:
                    fromindex = logList.index("from:")
                    frompoint = logList[fromindex + 1]
                    toindex = logList.index("to:")
                    topoint = logList[toindex + 1]
                    # 检查字典里连接这两个元素的数据流是否不止一条
                    testkey = "from " + frompoint + " to " + topoint
                    isMore = 0
                    for k in id_to_name_link.keys():
                        if testkey in k:
                            if 'number:' in k:
                                isMore = 1
                                break
                    if isMore == 0:
                        key = next((k for k, v in id_to_name_link.items() if
                                    (v.get('frompoint') == frompoint and v.get('topoint') == topoint)), None)
                    else:
                        key = next((k for k, v in id_to_name_link.items() if
                                (v.get('frompoint') == frompoint and v.get('topoint') == topoint and v.get('name') == text)), None)
                except:
                    frompoint = None
                    topoint = None
                    key = None
                datalogList.append(datalog("ShiftingLabel", "dataflow", starttime, endtime, key=key, old=(oldx, oldy),
                                           new=(newx, newy), frompoint=frompoint, topoint=topoint,
                                           routes=copy.deepcopy(tmpList), text=text))
                # 处理文本编辑过程缺失
                for i in range(len(datalogList) - 1, -1, -1):
                    # 如果先找到的是删除信息，说明该元素是删除后新添加的，还未被修改过text
                    if datalogList[i].type == 'Delete' and \
                            datalogList[i].category == 'dataflow' and \
                            datalogList[i].key == key:
                        break
                    if datalogList[i].type == 'TextEditing' and \
                            datalogList[i].category == 'dataflow' and \
                            datalogList[i].key == key:
                        if datalogList[i].text != datalogList[-1].text:
                            datalogList[i].text = datalogList[-1].text
                            if key in id_to_name_link:
                                id_to_name_link[key]['name'] = datalogList[-1].text
                        break

            # 删除元素
            elif re.match(r"\*  CommittedTransaction:  Delete", List[i]['content']):
                # print(id_to_name_node)
                # print(id_to_name_link)
                # print('delete!!!!!!!')
                # change_object_len = len(change_object.keys())
                for j in range(len(tmpList)):
                    # 如果删除的是节点
                    if "!mChangedEvent.Remove nodeDataArray" in tmpList[j]['content']:
                        # 找到元素名字的id
                        namepoint = j
                        log = tmpList[namepoint]['content']
                        logList = re.split(r"[ ]+", log)
                        name_id = logList[-1]
                        nameindex = logList.index("old:")
                        name = logList[nameindex + 1]
                        # print("delelte_node_id: "+ name_id)
                        # 找到对应的元素的唯一key
                        key = next((k for k, v in id_to_name_node.items() if
                                    (v.get('name') == name and v.get('name_id') == name_id)
                                    ), None)
                        if key is None:
                            key = next((k for k, v in id_to_name_node.items() if
                                        v.get('name') == name), None)
                        # print(name)
                        # print(key)
                        if key:
                            category = id_to_name_node[key]['category']
                            # change_object[change_object_len][key] = id_to_name_node[key]
                            change_object[key] = id_to_name_node[key]
                            print(id_to_name_node)
                            del id_to_name_node[key]
                            print("delete_node: ")
                            print("key: " + key + " cate: " + category)
                            print('name:' + name)
                            # 操作对象的文本内容
                            try:
                                textindex = logList.index("old:")
                                text = logList[textindex + 1]
                            except:
                                text = ""
                            starttime = tmpList[0]['timeStamp']
                            endtime = tmpList[-1]['timeStamp']
                            datalogList.append(datalog("Delete", category, starttime, endtime, key=key,
                                                       text=text, routes=copy.deepcopy(tmpList)))
                       # print(datalog)
                    # 如果删除的是数据流
                    elif "!mChangedEvent.Remove linkDataArray" in tmpList[j]['content']:
                        print(id_to_name_link)
                        # 找到元素名字的id
                        namepoint = j
                        log = tmpList[namepoint]['content']
                        logList = re.split(r"[ ]+", log)
                        name_id = logList[-1]
                        nameindex = logList.index("old:")
                        name = logList[nameindex + 1]
                        if name == '[object':
                            name = ''
                        print("delelte_flow_id: "+ name_id)
                        # 找到对应的元素的唯一key
                        key = next((k for k, v in id_to_name_link.items() if
                                    (v.get('name') == name and v.get('name_id') == name_id)
                                    ), None)
                        if key is None:
                            key = next((k for k, v in id_to_name_link.items() if
                                        v.get('name') == name), None)
                        print(name)
                        print(key)
                        if key:
                            category = id_to_name_link[key]['category']
                            # change_object[change_object_len][key] = id_to_name_link[key]
                            change_object[key] = id_to_name_link[key]
                            del id_to_name_link[key]
                            print("delete_flow: ")
                            print("key: " + key + " cate: " + category)
                            # 操作对象的文本内容
                            try:
                                textindex = logList.index("old:")
                                text = logList[textindex + 1]
                            except:
                                text = ""
                            if text == '[object':
                                text = ''
                            starttime = tmpList[0]['timeStamp']
                            endtime = tmpList[-1]['timeStamp']
                            datalogList.append(datalog("Delete", category, starttime, endtime, key=key,
                                                       text=text))
                       # print(datalog)

            elif re.match(r"\*  CommittingTransaction:  ChangeFromArrow", List[i]['content']):
                log = tmpList[0]['content']
                logList = re.split(r"[ ]+", log)
                # print(logList)
                oldindex = logList.index("old:")
                newindex = logList.index("new:")
                oldtext = logList[oldindex + 1]
                newtext = logList[newindex + 1]
                textindex = logList.index("text:")
                text = logList[textindex + 1]
                detail = None
                # 如果是对数据流进行操作
                if "from:" in logList:
                    fromindex = logList.index("from:")
                    frompoint = logList[fromindex + 1]
                    toindex = logList.index("to:")
                    topoint = logList[toindex + 1]
                    key = next((k for k, v in id_to_name_link.items() if
                                (v.get('frompoint') == frompoint and v.get('topoint') == topoint and v.get('name') == text)), None)
                    if key is not None:
                        if 'number:' in key:
                            datatflow_num = '\n' + key.split('\n')[-1]
                        else:
                            datatflow_num = ''
                        category = id_to_name_link[key]['category']
                        isBothway = id_to_name_link[key]['isBothway']
                        isReverse = id_to_name_link[key]['isReverse']
                        isBothway = ~isBothway
                        isReverse = ~isReverse
                        id_to_name_link[key]['isBothway'] = isBothway
                        id_to_name_link[key]['isReverse'] = isReverse
                        print('yesyes!arrowChange!!!!!!!!!!!')
                        # print('isR:' + isReverse + 'isB:' + isBothway)
                        # new_value = id_to_name_link.pop(key)
                        if not isBothway and not isReverse:
                            # key = 'from ' + frompoint + ' to ' + topoint + datatflow_num
                            detail = 'shape: one-way'
                        elif not isBothway and isReverse:
                            # key = 'from ' + topoint + ' to ' + frompoint + datatflow_num
                            detail = 'shape: one-way reverse'
                        elif isBothway and not isReverse:
                            # key = 'line ' + frompoint + ' to ' + topoint + datatflow_num
                            detail = 'shape: line'
                        elif isBothway and isReverse:
                            # key = 'from ' + frompoint + ' to ' + topoint + '\nfrom: ' + topoint + ' to ' + frompoint + datatflow_num
                            detail = 'shape: two-way'
                        # 更新字典中键名key
                        # print('changeKEY:' + key)
                        # id_to_name_link[key] = new_value
                    else:
                        print('Can\'t find dataflow key when ChangeFromArrow! from' + frompoint + ' to ' + topoint + ' text: ' + text)
                        print(id_to_name_link)
                        print('---------------end-----------')

                # 如果是对节点进行操作
                elif "key:" in logList:
                    keyindex = logList.index("key:")
                    key = logList[keyindex + 1]
                    try:
                        category = id_to_name_node[key]['category']
                    except:
                        category = None


                starttime = tmpList[0]['timeStamp']
                endtime = tmpList[-1]['timeStamp']
                datalogList.append(datalog("ChangingFromArrow", category, starttime, endtime, old=oldtext, new=newtext,
                                           routes=copy.deepcopy(tmpList), text=text, key=key, detail=detail))

            elif re.match(r"\*  CommittingTransaction:  ChangeToArrow", List[i]['content']):
                log = tmpList[0]['content']
                logList = re.split(r"[ ]+", log)
                # print(logList)
                oldindex = logList.index("old:")
                newindex = logList.index("new:")
                oldtext = logList[oldindex + 1]
                newtext = logList[newindex + 1]
                textindex = logList.index("text:")
                text = logList[textindex + 1]
                detail = None
                # 如果是对数据流进行操作
                if "from:" in logList:
                    fromindex = logList.index("from:")
                    frompoint = logList[fromindex + 1]
                    toindex = logList.index("to:")
                    topoint = logList[toindex + 1]
                    key = next((k for k, v in id_to_name_link.items() if
                                (v.get('frompoint') == frompoint and v.get('topoint') == topoint and v.get('name') == text)), None)
                    if key and 'number:' in key:
                        datatflow_num = '\n' + key.split('\n')[-1]
                    else:
                        datatflow_num = ''
                    category = id_to_name_link[key]['category']
                    isBothway = id_to_name_link[key]['isBothway']
                    isReverse = id_to_name_link[key]['isReverse']
                    isBothway = ~isBothway
                    id_to_name_link[key]['isBothway'] = isBothway
                    print('yesyes!arrowChange!!!!!!!!!!!')
                   # print('isR:' + isReverse + 'isB:' + isBothway)
                   # new_value = id_to_name_link.pop(key)
                    if not isBothway and not isReverse :
                        # key = 'from ' + frompoint + ' to ' + topoint + datatflow_num
                        detail = 'shape: one-way'
                    elif not isBothway and isReverse :
                        # key = 'from ' + topoint + ' to ' + frompoint + datatflow_num
                        detail = 'shape: one-way reverse'
                    elif isBothway and not isReverse:
                        # key = 'line ' + frompoint + ' to ' + topoint + datatflow_num
                        detail = 'shape: line'
                    elif isBothway and isReverse:
                        # key = 'from ' + frompoint + ' to ' + topoint + '\nfrom: ' + topoint + ' to ' + frompoint + datatflow_num
                        detail = 'shape: two-way'
                    # 更新字典中键名key
                    # print('changeKEY:' + key)
                    # id_to_name_link[key] = new_value

                # 如果是对节点进行操作
                elif "key:" in logList:
                    keyindex = logList.index("key:")
                    key = logList[keyindex + 1]
                    category = id_to_name_node[key]['category']


                starttime = tmpList[0]['timeStamp']
                endtime = tmpList[-1]['timeStamp']
                datalogList.append(datalog("ChangingToArrow", category, starttime, endtime, old=oldtext, new=newtext,
                                           routes=copy.deepcopy(tmpList), text=text, key=key, detail=detail))
            # 粘贴
            elif re.match(r"\*  CommittedTransaction:  Paste", List[i]['content']):
                print("paste")
                # print(tmpList)
                # print(id_to_name_node)
                pasteList = []
                node_info = []
                dataflow_info = []
                # 遍历tmplist的每个日志条目
                for j in range(len(tmpList)):
                    # 如果添加的是节点，记录节点的name和name_id
                    if "!mChangedEvent.Insert nodeDataArray" in tmpList[j]['content']:
                        namepoint = j
                        log = tmpList[namepoint]['content']
                        logList = re.split(r"[ ]+", log)
                        name_id = logList[-1]
                        nameindex = logList.index("new:")
                        name = logList[nameindex + 1]
                        new_entry = (name, name_id)
                        # 将新条目添加到列表中
                        node_info.append(new_entry)
                        print('pastenode_name_id: ' + name_id)
                        print(name)
                        # print(id_to_name_node)
                    # 如果添加的是数据流，记录节点的name和name_id
                    elif "!mChangedEvent.Insert linkDataArray" in tmpList[j]['content']:
                        namepoint = j
                        log = tmpList[namepoint]['content']
                        logList = re.split(r"[ ]+", log)
                        name_id = logList[-1]
                        nameindex = logList.index("new:")
                        name = logList[nameindex + 1]
                        new_entry = (name, name_id)
                        # 将新条目添加到列表中
                        dataflow_info.append(new_entry)
                        print('pasteflow_name_id: ' + name_id)
                        print(name)
                # 遍历tmplist的每个日志条目
                for j in range(len(tmpList)):
                    name = name_id = None
                    # 如果存在category和key信息，说明是节点
                    if "category:" in tmpList[j]['content'] and "key:" in tmpList[j]['content']:
                        # print(tmpList[j])
                        log = tmpList[j]['content']
                        logList = re.split(r"[ ]+", log)
                        categoryindex = logList.index("category:")
                        category = logList[categoryindex + 1]
                        starttime = tmpList[0]['timeStamp']
                        endtime = tmpList[-1]['timeStamp']
                        keyindex = logList.index("key:")
                        key = logList[keyindex + 1]
                        textindex = logList.index("text:")
                        # 提取text文本内容
                        try:
                            text = logList[textindex + 1]
                        # 如果该节点没有text，则令其为空
                        except:
                            text = ""
                        # 某些情况下text为空时name可能为key值，所以与loc后的值一致
                        object_nameindext = logList.index('loc:')
                        object_name = logList[object_nameindext + 1]
                        # 提取新的x，y坐标
                        newindex = logList.index("new:")
                        newx = logList[newindex + 1]
                        newy = logList[newindex + 2]
                        # 提取旧的x，y坐标
                        oldindex = logList.index("old:")
                        oldx = logList[oldindex + 1]
                        oldy = logList[oldindex + 2]
                        # print(node_info)
                        # 找到列表中包含text的值并返回name_id
                        for info in node_info:
                            if (info[0] is not None) and (text is not None) and (info[0] == object_name):
                                name = info[0]
                                name_id = info[1]
                                # print("info:")
                                # print(info)
                                node_info.remove(info)
                                break
                            name_id = None
                        # 创建元素，写入映射表
                        if name_id is not None and key not in id_to_name_node:
                            id_to_name_node[key] = {'name': name, 'name_id': name_id, 'category': category}
                            print(id_to_name_node[key])
                            print(name +' ' + name_id)
                            datalogList.append(
                                datalog("PastingNode", category, starttime, endtime, text=text, old=(oldx, oldy),
                                    new=(newx, newy),
                                    key=key, routes=copy.deepcopy(tmpList)))
                    # 如果不存在category和key信息。存在from信息，说明是数据流
                    elif "from:" in tmpList[j]['content']:
                        logList = re.split(r"[ ]+", tmpList[j]['content'])
                        fromindex = logList.index("from:")
                        frompoint = logList[fromindex + 1]
                        toindex = logList.index("to:")
                        topoint = logList[toindex + 1]
                        starttime = tmpList[0]['timeStamp']
                        endtime = tmpList[-1]['timeStamp']
                        # 获取操作对象的文本内容
                        try:
                            textindex = logList.index("text:")
                            text = logList[textindex + 1]
                        except:
                            text = ""
                            # 某些情况下text为空时name可能为key值，所以与points后的值一致
                        object_nameindext = logList.index('points:')
                        object_name = logList[object_nameindext + 1]
                        # print(text)
                        key = "from " + frompoint + " to " + topoint
                        # print("dataflow_info:")
                        # print(dataflow_info)
                        # 找到映射表中包含text的值并返回name_id
                        for info in dataflow_info:
                            if (info[0] is not None) and (text is not None) and (info[0] == object_name):
                                name = info[0]
                                name_id = info[1]
                                dataflow_info.remove(info)
                                break
                            name_id = None
                        # 创建元素，写入映射表
                        if name_id is not None:
                            if key not in id_to_name_link:
                                # 创建元素，写入映射表
                                id_to_name_link[key] = {'name': name, 'name_id': name_id, 'category': 'dataflow',
                                                        'frompoint': frompoint, 'topoint': topoint,
                                                        'isBothway': False, 'isReverse': False}
                                datalogList.append(datalog("PastingLink", "dataflow", starttime, endtime, key=key,
                                                         frompoint=frompoint, topoint=topoint, text=text))
                            else:
                                found = False
                                datatflow_num = 0
                                for k in id_to_name_link.keys():
                                    if key in k:
                                        if id_to_name_link[k]['name_id'] == name_id:
                                            found = True
                                            break
                                if not found:
                                    for k in id_to_name_link.keys():
                                        if key in k and 'number:' in k:
                                            numberindext = k.split().index('number:')
                                            value = int(k.split()[numberindext + 1])
                                            datatflow_num = max(datatflow_num, value)
                                    datatflow_num = datatflow_num + 1
                                    key = key + '\nnumber: ' + str(datatflow_num)
                                    # print(id_to_name_link[key])
                                    # print(name + ' ' + name_id)
                                    id_to_name_link[key] = {'name': name, 'name_id': name_id, 'category': 'dataflow',
                                                            'frompoint': frompoint, 'topoint': topoint,
                                                            'isBothway': False, 'isReverse': False}
                                    datalogList.append(datalog("PastingLink", "dataflow", starttime, endtime, key=key,
                                                 frompoint=frompoint, topoint=topoint, text=text))
                # print(id_to_name_node)
                # print(id_to_name_link)
                # print(pasteList)
                # print('paste end')
                # datalogList.append(datalog("Paste", None, tmpList[0]['timeStamp'], tmpList[-1]['timeStamp'],
                #                            routes=copy.deepcopy(tmpList), key=copy.deepcopy(pasteList)))
            # elif re.match(r"\*  from SourceChanged: ", List[i]['content']):
            #     print(List[i]['content'])
            #     # datalogList.append(datalog("SourceChanged", "?", starttime, endtime, routes=copy.deepcopy(tmpList)))
            # # else:
            # #     print(List[i]['content'])
            tmpList.clear()

    with open("log.txt", 'w', encoding="utf-8") as f:
        for item in datalogList:
            f.write(
                str(item.type) + ' ' + str(item.category) + ' ' + str(item.key) + ' ' + str(item.frompoint) + ' ' + str(
                    item.topoint) + ' ' +
                str(item.old) + ' ' + str(item.new) + ' ' + str(item.starttime) + '\n')
    # print(datalogList)
    tmplogList = []
    for index in range(len(datalogList)):
        # print(index, item)
        if index > 0:
            '''
            Merge two neighbour text editing.
            '''
            if datalogList[index].type == "TextEditing" and datalogList[index - 1].type == "TextEditing" \
                    and (
                    (datalogList[index].topoint == None and datalogList[index].key == datalogList[index - 1].key) or \
                    (datalogList[index].topoint is not None \
                     and datalogList[index - 1].topoint is not None \
                     and datalogList[index].frompoint is not None \
                     and datalogList[index - 1].frompoint is not None \
                     and datalogList[index].frompoint == datalogList[index - 1].frompoint \
                     and datalogList[index].topoint == datalogList[index - 1].topoint)):
                tmplogList[-1].new = datalogList[index].new
                tmplogList[-1].endtime = datalogList[index].endtime
                tmplogList[-1].text = datalogList[index].text
                continue
        tmplogList.append(copy.deepcopy(datalogList[index]))

    with open("log2.txt", 'w', encoding="utf-8") as f:
        for item in tmplogList:
            f.write(
                str(item.type) + ' ' + str(item.category) + ' ' + str(item.key) + ' ' + str(item.frompoint) + ' ' + str(
                    item.topoint) + ' ' +
                str(item.old) + ' ' + str(item.new) + ' ' + str(item.starttime) + '\n')
    '''
    Manage Undo and Redo. 
    '''
    # datalogList.clear()
    # undoList = []
    # # print(datalogList)
    # for index in range(len(tmplogList)):
    #     if tmplogList[index].type == "Undo":
    #         try:
    #             tmplogList[index].category = datalogList[-1].category
    #             tmplogList[index].key = datalogList[-1].key
    #             tmplogList[index].text = datalogList[-1].text
    #             tmplogList[index].starttime = datalogList[-1].starttime
    #             tmplogList[index].endtime = datalogList[-1].endtime
    #             undoList.append(datalogList[-1])
    #             print(datalogList[-1])
    #             # del datalogList[-1]
    #         except:
    #             pass
    #     elif tmplogList[index].type == 'Redo':
    #         try:
    #             # datalogList.append(undoList[-1])
    #             tmplogList[index].key = undoList[-1].key
    #             tmplogList[index].text = undoList[-1].text
    #             tmplogList[index].starttime = undoList[-1].starttime
    #             tmplogList[index].endtime = undoList[-1].endtime
    #             del undoList[-1]
    #         except:
    #             pass
    #     datalogList.append(tmplogList[index])

    # with open("log3.txt", 'w', encoding="utf-8") as f:
    #     for item in datalogList:
    #         f.write(
    #             str(item.type) + ' ' + str(item.category) + ' ' + str(item.key) + ' ' + str(item.frompoint) + ' ' + str(
    #                 item.topoint) + ' ' + str(item.text) + ' ' +
    #             str(item.old) + ' ' + str(item.new) + ' ' + str(item.starttime) + ' ' + str(item.endtime) + '\n')
    return tmplogList
    '''
    manage paste and delete repeat addlink
    '''
'''
    import numpy as np
    linkflag = np.zeros((100, 100), dtype=int)
    newtmploglist = []
    for index in range(len(datalogList)):
        if datalogList[index].type == "Paste":
            for item in datalogList[index].key:
                if item.type == "PastingLink":
                    if item.frompoint == "undefined" or item.topoint == "undefined":
                        continue
                    # print(item)
                    frompoint = int(item.frompoint) * -1
                    topoint = int(item.topoint) * -1
                    if linkflag[frompoint, topoint] == 0:
                        newtmploglist.append(item)
                        linkflag[frompoint, topoint] = 1
                else:
                    newtmploglist.append(item)
        else:
            newtmploglist.append(datalogList[index])

    with open("hehe.txt", 'w', encoding="utf-8") as f:
        for item in datalogList:
            f.write(
                str(item.type) + ' ' + str(item.category) + ' ' + str(item.key) + ' ' + str(item.frompoint) + ' ' + str(
                    item.topoint) + ' ' +
                str(item.old) + ' ' + str(item.new) + '\n')

    return datalogList
'''

'''
Some lines is lose, add some lines to complete the data.
'''


def addline(modelid):
    # 判断给定路径下是否存在指定的CSV文件
    if not os.path.exists("23springLogs/{}.csv".format(modelid)):
        return None
    # 读取该CSV文件，返回一个Pandas DataFrame对象
    df = pd.read_csv("23springLogs/{}.csv".format(modelid))
    # 创建一个空列表，用于存储解析后的日志信息
    List = []
    # 遍历DataFrame对象 中的每一行
    for row, item in df.iterrows():
        # print(item['content'])
        # 将当前行中的content列的JSON字符串解析为Python字典对象
        content = json.loads(item['content'])
        # 如果该日志行level字段值为C，则跳过
        if content['level'] == 'C':
            continue
        # 如果该日志行的content字段值在skipList列表中，则跳过
        if content['content'] in skipList:
            continue
        # 如果该日志行的content字段值匹配下列正则表达式，则跳过
        # if re.match(
        #         r"(!mChangedEvent.Insert nodeDataArray:  GraphLinksModel  new: 外部实体)|
        #         (!mChangedEvent.Insert nodeDataArray:  GraphLinksModel  new: 加工)|
        #         (!mChangedEvent.Insert nodeDataArray:  GraphLinksModel  new: 数据存储)|
        #         (!mChangedEvent.Insert linkDataArray:  GraphLinksModel  new: 数据流)",
        #         content['content']):
        #     continue
        # 如果该日志行的content字段值匹配下列正则表达式，则跳过
        if re.match(
                r"(!m to linkToKey)|(!m from linkFromKey)|(\*  to SourceChanged)|(\*  from SourceChanged)",
                content['content']):
            continue
        # 如果以上条件均不成立，则将当前解析出来的Python字典对象添加到List列表中
        List.append(content)

    # 按照时间戳将List列表中的字典对象进行排序
    List = sorted(List, key=cmp_time)
    # if __name__ == "__main__":
    #     with open("tmp.txt", 'w', encoding="utf-8") as f:
    #         for item in List:
    #             for spe in item:
    #                 f.write(str(item[spe]))
    #             f.write("\n")
    for row, item in enumerate(List):
        # 处理两次添加元素间缺少提交事务
        if re.match(r"!m loc: (外部实体|数据存储|加工)  old: 0 ", item['content']) and \
                re.match(r"!m loc: (外部实体|数据存储|加工)", List[row - 2]['content']) and \
                re.match(r"!mChangedEvent.Insert nodeDataArray:", List[row - 1]['content']):
            List.append({'content': '*  CommittedTransaction:  ExternalCopy', 'level': 'A', \
                         'timeStamp': List[row - 2]['timeStamp'], 'parentLog': List[row - 2]['parentLog']})
            print("yesyesyesy!!")
        # 处理两次resize元素间缺少提交事务
        if re.match(r"!m size:", item['content']) and \
            re.match(r"!m loc:", List[row - 1]['content']) and \
            re.split(r"[ ]+", item['content'])[2] != re.split(r"[ ]+", List[row - 1]['content'])[2]:
            List.append({'content': '*  CommittedTransaction:  Resizing', 'level': 'A', \
                         'timeStamp': List[row - 1]['timeStamp'], 'parentLog': List[row - 1]['parentLog']})
        # 处理修改文本内容与下次操作间缺少文本的提交事务
        if '!m text:' in item['content'] and \
                '!m text:' not in List[row + 1]['content'] and \
                '*  CommittedTransaction:  input text' not in List[row + 1]['content']:
            List.append({'content': '*  CommittedTransaction:  input text', 'level': 'A', \
                         'timeStamp': List[row]['timeStamp'], 'parentLog': List[row - 1]['parentLog']})
        # 处理单次添加元素缺少的提交事务
        if '!m loc:' in item['content'] and \
                '!m loc:' not in List[row + 1]['content'] and \
                 '!m points:' not in List[row + 1]['content'] and \
                 '!m size:' not in List[row + 1]['content'] and \
                 '!mChangedEvent' not in List[row + 1]['content'] and \
                 '*  CommittedTransaction:' not in List[row + 1]['content']:
            List.append({'content': '*  CommittedTransaction:  ExternalCopy', 'level': 'A', \
                         'timeStamp': List[row]['timeStamp'], 'parentLog': List[row]['parentLog']})
            print("add 单次添加元素提交事务!!")


    List = sorted(List, key=cmp_time)
    # print(List)
    with open("data.csv", 'w', encoding="utf-8") as f:
        for item in List:
            for spe in item:
                f.write(str(item[spe]))
            f.write("\n")
    return List


def getXY(modelid=None, datalogList=None):
    # Count how many edit text before adding link.
    # X = named node link to named node
    # Y = named node link to unnamed node
    # Z = unnamed node link to unnamed node
    if datalogList == None:
        datalogList = read(modelid)
    dic = {}
    XYList = ""
    for item in datalogList:
        if item.type == "TextEditing":
            dic[item.key] = True
        elif item.type == "AddingLink":
            if item.frompoint not in dic:
                dic[item.frompoint] = False
            if item.topoint not in dic:
                dic[item.topoint] = False
            if dic[item.frompoint] == True:
                if dic[item.topoint] == True:
                    XYList += "X"
                else:
                    XYList += "Y"
            else:
                if dic[item.topoint] == True:
                    XYList += "Y"
                else:
                    XYList += "Z"
    return XYList


def getTextEditing(modelid, datalogList=None):
    # Count how many text editing.
    if datalogList == None:
        datalogList = read(modelid)
    # print(datalogList)
    cntnode = 0
    cntlink = 0
    for item in datalogList:
        if item.type == "TextEditing":
            if item.category == "dataflow":
                cntlink += 1
            else:
                cntnode += 1
    return cntnode, cntlink, len(datalogList)


def classification(modelid, datalogList=None):
    # 分级
    if datalogList == None:
        datalogList = read(modelid)
    nodeList = []
    for index in range(len(datalogList) - 1, -1, -1):
        # print(len(datalogList))
        # print(index)
        item = datalogList[index]
        if item.type == "AddingNode":
            if item.key not in nodeList:
                nodeList.insert(0, item.key)
    return nodeList


def read(modelid):
    List = addline(modelid)
    if List == None:
        return []
    print("READING " + str(modelid))
    datalogList = solve(List)
    adjLog = ["Resizing", "MovingNode", "LinkShifting", "ShiftingLabel", "LinkReshaping"]
    return datalogList


# output:每个文件是同一个人从头到尾的操作，english name
def get_original_op():
    # 获取文件夹"./23springLogs"下的所有文件名，并存储到dirs列表中
    dirs = os.listdir("./23springLogs")
    # 创建一个空列表filenames，用于后续存储去除“.csv”后缀的文件名
    filenames = []
    i = 0
    # 循环遍历dirs列表中的所有文件名
    for test1 in dirs:
        # 使用正则表达式（re模块）将文件名中的“.csv”后缀去掉，只保留前面的部分
        test1 = re.split(r'.csv', test1)
        # 将去掉后缀的文件名存储到filenames列表中
        filenames.append(test1[0])
        # 使用“read”函数读取文件名对应的文件内容
        raw = read(test1[0])
        # print(raw)
        # print("原始数据结束")
        # 取出每个type和category
        dllist = []
        # 遍历文件内容中的每行
        for i, dl in enumerate(raw):
            # 如果该行有category属性，则将type和category结合为一个新的字符串
            if dl.category != None:
                dllist.append([dl.type + "_" + dl.category])
            # 如果该行没有category属性，则直接使用type作为字符串
            else:
                dllist.append([dl.type])
            dllist.append([dl.text])
            dllist.append([dl.key])
            dllist.append([dl.detail])
            dllist.append([dl.starttime])
            dllist.append([dl.endtime])
        # print("总类型")
        # 输出处理后的类型列表
        # print(dllist)

        # 打开一个新的CSV文件， 文件名为去掉后缀的文件名
        with open("./{}.csv".format(test1[0]), "w", newline="", encoding="utf-8") as f:
            # 使用CSV模块创建一个写入器
            wr = csv.writer(f)
            # 写入CSV文件的第一行，动作、操作对象文本内容、操作开始时间、操作结束时间、操作持续时间、两操作间隔时间
            wr.writerow(["Type", "text", "key", "detail", "starttime", "endtime", "time_duration(seconds)", "time_interval(seconds)"])
            # 记录上一个操作的结束时间
            last_endtime = None
            # 循环遍历处理后的类型列表中的每个元素
            for i in range(0, len(dllist), 6):
                starttime = dllist[i + 4][0]
                endtime = dllist[i + 5][0]
                # 操作持续时间
                time_duration = duration(starttime, endtime)
                # 两操作间隔时间
                time_interval = duration(last_endtime, starttime) if last_endtime is not None else ""
                last_endtime = endtime
                # 转换时间格式
                starttime, endtime = trans_date(starttime, endtime)
                wr.writerow([dllist[i][0], dllist[i + 1][0], dllist[i + 2][0], dllist[i + 3][0], starttime, endtime, time_duration,
                             time_interval])



def main():
    get_original_op()


if __name__ == "__main__":
    main()
