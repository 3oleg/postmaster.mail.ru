import requests,pickle
from time import time

login='ololo@mail.ru'
password='ololopas'
pickle_file='last_data.bin'
grafana_host='ololografana'
sitenames=['ololosite.ru','ololosite88.ru']

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
            blocklink = item.findAll("a")
            if blocklink:
                sitename=blocklink[1].text
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
        #Our servers has FQDN hostnames
        datacenter = re.search(r'[A-z]+', hostname[1]).group(0)

        # Prefix path of resourse in collectd
        path_to_data='%s.%s.%s.mailru' % (datacenter, hostname[1], hostname[0])
        data=""
        # Output result must be counts/1minute for all cron periods
        k=(self.timenow-float(self.pickleobjects["lasttime"]))/60
        for i in self.data:
            for j in self.pickleobjects["data"]:
                if i["sitename"]==j["sitename"] and i["sitename"]in sitenames:
                    data+='%s.%s.total %d %d \n' % (path_to_data,i["sitename"].replace('.', '_'),(i["total"]-j["total"])/k,self.timenow)
                    data+='%s.%s.spam %d %d \n' % (path_to_data,i["sitename"].replace('.', '_'),(i["spam"]-j["spam"])/k,self.timenow)

        print(data)
        conn = socket.create_connection((grafana_host, 2003))
        conn.sendall(data.encode())
        conn.close()


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