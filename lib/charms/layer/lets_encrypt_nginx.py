from crontab import CronTab

config = {
    'renew': 'lets-encrypt-renew',
    'reload': 'nginx-reload'
}

def create_crontab():
    cron = CronTab(user='root')
    jobRenew = cron.new(command='/usr/bin/letsencrypt renew >> /var/log/le-renew.log', comment=config['renew'])
    jobRenew.setall('30 2 * * 1')
    jobRenew.enable()
    jobReload = cron.new(command='/bin/systemctl reload nginx', comment=config['reload'])
    jobReload.setall('35 2 * * 1')
    jobReload.enable()
    cron.write()

def delete_crontab():
    cron = CronTab(user='root')
    for key in config.keys():
        jobs = cron.find_comment(config[key])
        for job in jobs:
            cron.remove(job)
    cron.write()