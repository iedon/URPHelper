#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Date    : 2017-07-29 16:53:19
# @Author  : mayongze (1014057907@qq.com)
# @Link    : https://github.com/mayongze
# @Version : 1.1.1.20170705

import os
import DBHelper
import URPCrawlerDAO
import traceback
import asyncio,aiohttp
import userapiconfig
import NETinterface as NET
import log
import time
from multiprocessing import Process, Queue
from threading import Thread


class MyPipeline(object):
    def __init__(self, loop, q, _log):
        self.loop = loop
        self.q = q
        self.logPip = _log
        self.sem = asyncio.Semaphore(21)
        # limit_per_host=30  limit = 100
        conn  =  aiohttp.TCPConnector (verify_ssl=False,limit_per_host = 30,use_dns_cache=True,loop = self.loop)
        self.session = aiohttp.ClientSession(loop = self.loop,connector = conn)
        self.NETlog = log.set_logger(filename = "netinterface.log", isOnlyFile = False)
        self.netstatus = 0

    # 消费者协程
    def process_localDB(self):
        yield from URPCrawlerDAO.process(dataFilePath = userapiconfig.SQLITE_PATH,logfilename = userapiconfig.SQLITE_LOG_PATH)
        URPCrawlerDAO.endCommit()

    async def process_NET(self,role):
        #if not isinstance(role, str):
        self.netstatus = self.netstatus + 1
        # look = await self.sem
        await NET.push(self.session,role,self.NETlog)
        # look.__exit__()
        self.netstatus = self.netstatus - 1

def start_loop(loop):
    '''线程循环'''
    asyncio.set_event_loop(loop)
    loop.run_forever()

# 存储调度
def main(q , pindex = 1):
    logPip = log.set_logger(filename = "URPPipelines.log", isOnlyFile = False)
    loop = asyncio.new_event_loop()
    process = MyPipeline(loop, q, logPip)

    cDB = process.process_localDB()
    cDB.send(None)

    t = Thread(target=start_loop, args=(loop,))
    t.setDaemon(True)
    t.start()

    index = 0
    while True:
        try:
            role = q.get()
            # 写sqlite
            cDB.send((role,index))
            # 写微信端
            asyncio.run_coroutine_threadsafe(process.process_NET(role), loop)
        except StopIteration :
            cDB.close()
            logPip.info('数据存储结束! -- %s' % process.netstatus)
            break
        except Exception as e:
            logPip.error(traceback.format_exc())
        else:
            pass
        finally:
            index = index + 1

    while True:
        # NET 上传结束标志
        if process.netstatus == 0:
            process.session.close()
            break
        logPip.error('等待微信端上传！-- %s' % process.netstatus)
        time.sleep(30)
    loop.stop()
    logPip.error('所有任务结束！')
    # process.session.close()

if __name__ == '__main__':
    pass
    logPip = log.set_logger(filename = "URPPipelines.log", isOnlyFile = False)
    loop = asyncio.new_event_loop()
    process = MyPipeline(loop, None, logPip)