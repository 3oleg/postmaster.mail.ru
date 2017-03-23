import requests,pickle
from time import time
from settings import *

class parsemailru():
    def __init__(self,login,password):
        self.formdata = self.resp = ''
        self.r=requests.session()
        self.login=login
        self.password=password

    def getcontent(self):
        if self.formdata:
            self.resp = self.r.post('https://auth.mail.ru/cgi-bin/auth',
                  headers={'referer': 'https://postmaster.mail.ru/','User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.110 Safari/537.36'},
                  data=self.formdata,
                  ).content.decode('utf-8')
        else:
            self.r.cookies=self.pickleobjects["cookies"]
            self.resp=self.r.get('https://postmaster.mail.ru/',
                       headers={'referer': 'https://postmaster.mail.ru/',
                                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.110 Safari/537.36'},
                       ).content.decode('utf-8')
        self.pickleobjects["cookies"]=self.r.cookies
        self.timenow=time()

    def getdata(self):
        from bs4 import BeautifulSoup
        self.data=[]
        soup = BeautifulSoup(self.resp, "html.parser")
        ourtable = soup.find("table", {"class": "statistic-table"})
        if not ourtable:
            return False
        for item in ourtable.findAll("tr"):
            blocklink = item.findAll("a", {"class": ""})
            if blocklink:
                sitename=blocklink[-1].text
                total = item.find("td", {"class": "statistic-table__total statistic-table__item"}).text.replace('\xa0', '')
                if not total:total=0
                spam = item.find("td", {"class": "statistic-table__click-spam"}).text.replace('\xa0', '')
                if not spam:spam=0
                self.data.append({"sitename":sitename,"total":int(total),"spam":int(spam)})


        #for i in self.data:
        #    print("%s: %s" % (i["sitename"],i["total"]))
        return True

    def writepickle(self,file="last_data.bin"):
        with open(file, 'wb') as f:
            pickle.dump(self.pickleobjects,f)

    def load_from_pickle(self,file="last_data.bin"):
        try:
            with open(file, 'rb') as f:
                self.pickleobjects=pickle.load(f)
                if not "cookies" in self.pickleobjects or not "lasttime" in self.pickleobjects:
                    raise("Not correct pickle file")
        except:
            self.pickleobjects={"lasttime":time()}
            self.formdata={'new_auth_form': '1', 'page': 'https://postmaster.mail.ru/', 'post': '', 'login_from': '',
                        'Login': self.login, 'Domain': 'mail.ru', 'Password': self.password}


    def send_to_grafana(self,grafana_host):
        if not "data" in self.pickleobjects:
            self.pickleobjects["data"] = self.data
            return

        '''Procedure to calculate count avg value of statuses and send it to grafana'''
        import socket,re,time
        hostname = socket.gethostname().split(".")
        #hostname = ['mx1-1','sd37','ru']
        #Our servers has FQDN hostnames
        datacenter = re.search(r'[A-z]+', hostname[1]).group(0)

        # Prefix path of resourse in collectd
        path_to_data='%s.%s.%s.mailru' % (datacenter, hostname[1], hostname[0])
        msg=""
        # Output result must be counts/1minute for all cron periods
        k=(self.timenow-float(self.pickleobjects["lasttime"]))/60
        for i in self.data:
            for j in self.pickleobjects["data"]:
                if i["sitename"]==j["sitename"] and i["sitename"]in sitenames:
                    total=(i["total"]-j["total"])/k
                    spam=(i["spam"]-j["spam"])/k
                    if total >0 and spam > 0:
                        msg+='%s.%s.total %d %d \n' % (path_to_data,i["sitename"].replace('.', '_'),total,self.timenow)
                        msg+='%s.%s.spam %d %d \n' % (path_to_data,i["sitename"].replace('.', '_'),spam,self.timenow)

        print(msg)
        conn = socket.create_connection((grafana_host, 2003))
        conn.sendall(msg.encode())
        conn.close()
        #Запоминаем последнийе параметры в переменную - славарь, которую потом запишем в файл
        self.pickleobjects["data"] = self.data
        self.pickleobjects["lasttime"] = self.timenow

if __name__=="__main__":
    cls=parsemailru(login,password)
    cls.load_from_pickle(pickle_file)
    cls.getcontent()
    #если на странице не нашлась нужная таблица, сбрасываем куки и авторизируемся еще раз
    if not cls.getdata():
        cls.load_from_pickle('')
        cls.getcontent()
        cls.getdata()
    cls.send_to_grafana(grafana_host)
    cls.writepickle(pickle_file)
