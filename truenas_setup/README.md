# TrueNAS SCALE Server Setup Guide

This guide outlines the steps to configure your "Utility & Home Hub" server using TrueNAS SCALE. This server will act as the central storage and 24/7 service hub for your entire AI ecosystem.

---

### Phase 1: Install TrueNAS SCALE

1.  **Download:** Get the latest version of [TrueNAS SCALE](https://www.truenas.com/truenas-scale/) (choose the SCALE version, not CORE).
2.  **Create Bootable USB:** Use a tool like [Rufus](https://rufus.ie/) or [BalenaEtcher](https://www.balena.io/etcher/) to write the downloaded `.iso` file to a USB drive.
3.  **Install:** Boot the Utility Hub server from the USB drive and follow the on-screen instructions.
    *   **Recommendation:** Install the TrueNAS OS onto a small, dedicated boot drive (like a small SSD or a mirrored pair of them). Do not install it on the large hard drives you intend to use for data storage.

---

### Phase 2: Configure Storage

Once TrueNAS is installed and you've accessed the web UI, your first task is to set up the storage.

1.  **Create a Storage Pool:**
    *   Navigate to `Storage` -> `Pools`.
    *   Click `Add` and create a new pool. Give it a name like `mainpool`.
    *   Select all your large data drives and arrange them in a ZFS layout. For a mix of performance and redundancy, `RAIDZ2` (similar to RAID 6) is a great choice if you have enough drives.
2.  **Create Datasets:**
    *   Datasets are like folders, but with special properties. They are the best way to organize your data.
    *   In your new `mainpool`, create the following datasets:
        *   `mainpool/apps` (This will store the configuration data for all your apps like Home Assistant, n8n, etc.)
        *   `mainpool/media` (For movies, music, etc., to be used by Plex/Jellyfin)
        *   `mainpool/downloads`
        *   `mainpool/backups`
        *   `mainpool/ai_data` (A parent dataset for all AI-related shares)

3.  **Create Child Dataset for AI:**
    *   Inside `mainpool/ai_data`, create another dataset named `file_intake`. This is the critical folder that the AI Powerhouse will connect to.

---

### Phase 3: Set Up Network Sharing (NFS)

To allow the AI Powerhouse to access the `file_intake` folder, we need to share it over the network. NFS is the best choice for this Linux-to-Linux connection.

1.  **Enable NFS Service:** Go to `System Settings` -> `Services` and ensure the `NFS` service is running and set to start on boot.
2.  **Create the NFS Share:**
    *   Go to `Shares` -> `NFS Shares`.
    *   Click `Add`.
    *   For the `Path`, browse to and select `/mnt/mainpool/ai_data`.
    *   In the advanced options, you may need to add the IP address of your AI Powerhouse server to the "Authorized Networks" or similar field to grant it access.
    *   Save the share.

---

### Phase 4: Install Applications

TrueNAS SCALE uses a system called "Apps" to run Docker containers. This is where you will install all the services previously in the `utility_hub` compose file.

1.  **Navigate to Apps:** Go to the `Apps` section in the TrueNAS UI.
2.  **Install Apps:** Use the "Available Applications" tab to find and install the following. When you install them, you will be asked where to store their configuration data; point this to a new directory inside your `mainpool/apps` dataset.
    *   `homeassistant`
    *   `n8n`
    *   `prometheus`
    *   `grafana`
    *   `loki`
    *   `alertmanager`
    *   `mosquitto` (search for an MQTT broker app)
    *   `frigate` (when you are ready for Phase 7)

---

### Phase 5: Users & Permissions

For good security, it's best to create a dedicated user for your applications.

1.  **Create a User:** Go to `Credentials` -> `Local Users` and create a new user (e.g., `app_user`).
2.  **Set Permissions:** Go back to `Storage` -> `Pools` and edit the permissions for your `mainpool/apps` dataset. Give your new `app_user` read/write access. You will need to configure your apps to run as this user.

This guide provides the foundational steps. You now have a robust storage and services hub ready to support your AI Powerhouse.
