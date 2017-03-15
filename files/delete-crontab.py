from crontab import CronTab

def main():
    cron = CronTab(user='root')
    comments = ['lets-encrypt-renew', 'nginx-reload']
    for comment in comments:
    	jobs = cron.find_comment(comment)
    	for job in jobs:
    		cron.remove(job)
    cron.write()
    

if __name__ == '__main__':
    main()