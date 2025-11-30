# Media Stack Setup

This directory contains the `docker-compose.yml` to set up the media stack (Jellyfin, Radarr, Sonarr, etc.).

### Instructions for Target Server

1.  **Copy this directory** to your home folder on the target server (the VM with the GPU). A command like this will work from your local machine:
    `scp -r ./media_stack user@your_server_ip:~`

2.  **SSH into the target server/VM.**

3.  **Create the required data directories:**
    ```bash
    sudo mkdir -p /srv/data/{media/movies,media/tv,downloads,config/jellyfin,config/radarr,config/sonarr,config/prowlarr,config/qbittorrent}
    sudo chown -R 1000:1000 /srv/data
    ```
    *(Note: We are using user/group ID 1000. If your primary user on that machine is different, you may need to adjust the `chown` command or the `PUID`/`PGID` variables in the `docker-compose.yml` file.)*

4.  **Navigate into this directory** and start the services:
    ```bash
    cd media_stack
    docker-compose up -d
    ```

5.  **Access the services** in your browser at `http://<SERVER_IP>:<PORT>`:
    *   **Jellyfin:** Port `8096`
    *   **Sonarr:** Port `8989`
    *   **Radarr:** Port `7878`
    *   **Prowlarr:** Port `9696`
    *   **qBittorrent:** Port `8080` (Default user/pass: admin/adminadmin)
