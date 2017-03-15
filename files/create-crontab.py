from crontab import CronTab

def main():
    cron = CronTab(user='root')
    jobRenew = cron.new(command='/usr/bin/letsencrypt renew >> /var/log/le-renew.log', comment='lets-encrypt-renew')
    jobRenew.setall('30 2 * * 1')
    jobRenew.enable()

    jobReload = cron.new(command='/bin/systemctl reload nginx', comment='nginx-reload')
    jobReload.setall('35 2 * * 1')
    jobReload.enable()

    cron.write()

if __name__ == '__main__':
    main()