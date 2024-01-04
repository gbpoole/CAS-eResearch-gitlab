# CAS-eResearch Gitlab Application

## Installation on Nectar VM

The following instructions have been validated with a Nectar VM configured as follows:

Flavour Name: t3.xsmall
Image Name: NeCTAR Ubuntu 22.04 LTS (Jammy) amd64
Security Groups: Add SSL Security Group which supplies:
ALLOW IPv4 22/tcp from 0.0.0.0/0
ALLOW IPv4 443/tcp from 0.0.0.0/0
ALLOW IPv4 80/tcp from 0.0.0.0/0
ALLOW IPv6 to ::/0
ALLOW IPv4 to 0.0.0.0/0
ALLOW IPv4 8080/tcp from 0.0.0.0/0

### VM Config

In what follows, you will need the following, once the VM is instantiated:

* IP Address: available from the dashboard
* A project password to access the NeCTAR Cloud using the OpenStack API.  From the dashboard: > Settings > Reset Password

### Repo install

* Locally:
    * Make sure your nectar key has been enabled locally with `ssh-add <path/to/key>`
    * Copy a valid github key to the VM with: scp KEYNAME* ubuntu@IP_ADDRESS:/home/ubuntu/.ssh/
* On the VM:
    * Start the ssh agent with: eval "$(ssh-agent)"
    * Add the key to the agent: ssh-add .ssh/KEYNAME
    * Clone the REPO: git clone git@github.com:gbpoole/cas-eresearch-gitlab.git
    * Optionally, if you will edit the code locally, you'll want to do the following:

git config --global user.name "Your Name"
git config --global user.email "your@email.address"
git config --global core.editor "vi"
git remote set-url origin git@github.com:gbpoole/cas-eresearch-slack.git

# Install requirements

* Install Docker with: sudo ./cas-eresearch-slack/scripts/install_Docker_on_Ubuntu.sh (enter y-and-return when prompted)
* Install Python with: sudo ./cas-eresearch-slack/scripts/install_Python_on_Ubuntu.sh (enter y-and-return when prompted)
* Install the OpenStack client: sudo ./cas-eresearch-slack/scripts/install_OpenStack_client.sh
* Install certbot: sudo ./cas-eresearch-slack/scripts/install_certbot_on_Ubuntu.sh (enter y-and-return when prompted)
* Install Nginx: sudo ./cas-eresearch-slack/scripts/install_Nginx_on_Ubuntu.sh (enter y-and-return when prompted)
* Install Poetry with: sudo ./cas-eresearch-slack/scripts/install_Poetry.sh

### Set-up DNS name

* Install Open Stack CLI client:
	* Obtain Open Stack rc file from the dashboard: from the top bar, click on email and then OpenStack rc file download
	* scp rc file to the VM: scp rc-file-name.sh ubuntu@IP_ADDRESS:/home/ubuntu/
	* source the file on the VM: . rc-file-name.sh (enter project password when asked)
* Execute the following with the client:
	* check that your project has the default zone as follows: $ openstack zone list
	* add a DNS record for your instance to the zone as follows: $ openstack recordset create <project>.cloud.edu.au. <instance name> --type A --record <instance IP addr>
		* If a "Duplicate RecordSet" error is thrown, then you need to delete the old one first: openstack recordset delete <project>.cloud.edu.au.  <instance name>.<project>.cloud.edu.au.
		* then, retry the openstack recordset create command above

### Set-up Nginx

* Verify that Nginx registered itself as a service with ufw when it installed: sudo ufw app list
	* You should see something like:

Available applications:
  Nginx Full
  Nginx HTTP
  Nginx HTTPS
  OpenSSH

* Verify that Nginx was started at the install: systemctl status nginx
	* You should see something like:

● nginx.service - A high performance web server and a reverse proxy server
     Loaded: loaded (/lib/systemd/system/nginx.service; enabled; vendor preset: enabled)
     Active: active (running) since Wed 2022-08-03 04:35:19 UTC; 3min 17s ago
       Docs: man:nginx(8)
    Process: 44621 ExecStartPre=/usr/sbin/nginx -t -q -g daemon on; master_process on; (code=exited, status=0/SUCCESS)
    Process: 44631 ExecStart=/usr/sbin/nginx -g daemon on; master_process on; (code=exited, status=0/SUCCESS)
   Main PID: 44632 (nginx)
      Tasks: 2 (limit: 1144)
     Memory: 5.1M
     CGroup: /system.slice/nginx.service
             ├─44632 nginx: master process /usr/sbin/nginx -g daemon on; master_process on;
             └─44633 nginx: worker process

Aug 03 04:35:19 cas-eresearch-slack systemd[1]: Starting A high performance web server and a reverse proxy server...
Aug 03 04:35:19 cas-eresearch-slack systemd[1]: Started A high performance web server and a reverse proxy server.

* Copy Nginx config files into place: sudo cp scripts/nginx.config /etc/nginx/sites-available/cas-eresearch-slack
* Make a link to this file: sudo ln -s /etc/nginx/sites-available/cas-eresearch-slack /etc/nginx/sites-enabled/
* remove the default site (note, a copy will remain at rm /etc/nginx/sites-available/default if you need it): sudo rm /etc/nginx/sites-enabled/default
* Restart Nginx: sudo systemctl restart nginx.service
* Start site: gunicorn -b 0.0.0.0:8080 -w 4 -k uvicorn.workers.UvicornWorker app.main:app

### Set-up a "Let's Encrypt" Certificate

** Certbot only works with Python 3.5 to 3.8, so watch-out for the install of Python 3.10 above! **
** The following commands, for switching python3 versions might be handy: sudo update-alternatives  --set python3 /usr/bin/python3.10
 and sudo update-alternatives  --set python3 /usr/bin/python3.8 **

Create a new venv and run certbot from there:

python3 -m venv myenv
. ./myenv/bin/activate
pip3 install certbot certbot-nginx
sudo myenv/bin/certbot --nginx -d cas-eresearch-slack.adacs-gpoole.cloud.edu.au

For a 1-time renewal: sudo certbot renew

### Auto-renewal of SSL

Edit the following 2 files (`sudo vi`):

`/etc/systemd/system/certbot.service`
```
[Unit]
Description=Let's Encrypt renewal

[Service]
Type=oneshot
ExecStart=/usr/bin/certbot renew --quiet --agree-tos
ExecStartPost=/bin/systemctl reload apache2.service
```

`/etc/systemd/system/certbot.timer`
```
[Unit]
Description=Twice daily renewal of Let's Encrypt's certificates

[Timer]
OnCalendar=0/12:00:00
RandomizedDelaySec=1h
Persistent=true

[Install]
WantedBy=timers.target
```

Enable and start certbot.timer
```
systemctl enable --now certbot.timer
```

To check the status of the timer: `sudo systemctl status certbot.timer`

### Run the app

* Install Poetry.  Add to path: export PATH="/home/ubuntu/.local/bin:$PATH"
* Create a venv (if not done already): ./scripts/create_venv.sh
* Source venv: source venv/bin/activate
* Install the app with: poetry install
* To use docker-compose to start the app (from the repo directory): sudo docker-compose up -d
* Otherwise: gunicorn app.main:app -c gunicorn.nectar.conf.py
