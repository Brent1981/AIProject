# Hogwarts Castle - Self-Hosted Services Dashboard

You have successfully created the files for a central dashboard to access your self-hosted services. This guide will walk you through the setup process.

## File Overview

*   `index.html`: The main dashboard page. You can edit this file to add, remove, or change the services listed.
*   `nginx-example.conf`: An example Nginx configuration file. You **must** edit this file to match your network and then use it to configure your Nginx server.

## Setup Instructions

Follow these steps to get your dashboard running and accessible from `www.hogwarts-castle.com`.

### Step 1: Domain and DNS

1.  **Point Your Domain:** Log in to your domain registrar (where you bought `hogwarts-castle.com`) and create an **A record**. Point it to the public IP address of your home network.
2.  **Dynamic DNS (Recommended):** If your home IP address changes, consider using a dynamic DNS (DDNS) service to automatically keep your A record updated.

### Step 2: Place the Dashboard Files

1.  **Create a Web Root:** On your Nginx server, create a directory to store the website. The configuration example uses `/var/www/hogwarts-castle`.
    ```bash
    sudo mkdir -p /var/www/hogwarts-castle
    ```
2.  **Copy the HTML file:** Move the `index.html` file into this new directory.
    ```bash
    sudo cp index.html /var/www/hogwarts-castle/
    ```

### Step 3: Configure Nginx Reverse Proxy

1.  **Copy the Configuration:** Copy the provided `nginx-example.conf` to your Nginx `sites-available` directory. It's a good practice to rename it to match your domain.
    ```bash
    sudo cp nginx-example.conf /etc/nginx/sites-available/hogwarts-castle.com.conf
    ```
2.  **EDIT THE CONFIGURATION:** This is the most important step. Open the file with a text editor and modify it for your environment.
    ```bash
    sudo nano /etc/nginx/sites-available/hogwarts-castle.com.conf
    ```
    *   Find every `proxy_pass` directive.
    *   Change the placeholder IP addresses and ports (e.g., `http://192.168.1.10:8123/`) to the **actual internal IP addresses and ports** of your services (Home Assistant, Proxmox, etc.).

3.  **Enable the Site:** Create a symbolic link from `sites-available` to `sites-enabled`.
    ```bash
    sudo ln -s /etc/nginx/sites-available/hogwarts-castle.com.conf /etc/nginx/sites-enabled/
    ```

### Step 4: Secure Your Site with SSL (Let's Encrypt)

1.  **Install Certbot:** If you don't have it, install Certbot, which automates getting free SSL certificates.
    ```bash
    sudo apt update
    sudo apt install certbot python3-certbot-nginx
    ```
2.  **Run Certbot:** Certbot will automatically detect your domain from the Nginx config, get a certificate, and configure Nginx to use it.
    ```bash
    sudo certbot --nginx -d www.hogwarts-castle.com
    ```
    The example `nginx-example.conf` is already set up to use the paths where Certbot places the certificates.

### Step 5: Port Forwarding

1.  **Log in to your Router:** Access your router's administration page.
2.  **Forward Ports:** Find the "Port Forwarding" or "Virtual Server" section.
3.  **Create Rules:** Forward incoming traffic on ports **80 (HTTP)** and **443 (HTTPS)** to the **internal IP address of your Nginx server**.

### Step 6: Test and Reload

1.  **Test Nginx Configuration:** Before applying the changes, run a test to make sure there are no syntax errors.
    ```bash
    sudo nginx -t
    ```
2.  **Reload Nginx:** If the test is successful, reload Nginx to apply all the changes.
    ```bash
    sudo systemctl reload nginx
    ```

## Security Best Practices (CRITICAL)

You are exposing sensitive services to the internet. The reverse proxy is a good first step, but you should strongly consider adding a dedicated authentication layer.

*   **Authentication Proxy:** Use a tool like **[Authelia](https://www.authelia.com/)** or **[Pomerium](https://www.pomerium.com/)**. These sit in front of your services and require a single, secure login (with optional two-factor authentication) before a user can even reach the service's login page. This protects you from attacks and unauthorized access attempts.

Your dashboard should now be live at `https://www.hogwarts-castle.com`.
