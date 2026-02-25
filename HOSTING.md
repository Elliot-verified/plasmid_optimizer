# Hosting with PepMLM-650M (e.g. on GCP)

To run the plasmid optimizer **with** PepMLM (novel peptide generation), you need a host that can load the ~650M-parameter model. Vercel’s serverless limit (~500MB) is too small. This guide uses **GCP** to store the model and run the app.

**Bucket used in examples:** `plasmidgo` (your GCP Storage bucket).

## 1. Save the model to Google Cloud Storage (GCS)

Do this once from a machine with enough disk and network (e.g. your laptop or a small GCE VM).

### 1.1 Create a GCS bucket (or use existing plasmidgo)

If you already have bucket **plasmidgo**, skip to 1.2. Otherwise:

```bash
export GCP_PROJECT=your-project-id
gcloud config set project $GCP_PROJECT
gsutil mb -p $GCP_PROJECT -l US gs://plasmidgo/
```

### 1.2 Download the model and upload to GCS

From the project root, with ML deps installed:

```bash
pip install -e ".[ml]"
python scripts/export_pepmlm_for_gcs.py --output ./pepmlm-650m
gsutil -m cp -r ./pepmlm-650m gs://plasmidgo/pepmlm-650m
```

You can delete the local `./pepmlm-650m` folder after upload to save disk space.

---

## 2. Run the app on GCP and load the model from GCS

Two practical options: **Cloud Run** (serverless, scales to zero) or a **GCE VM** (always-on, good if you want a persistent cache).

### Option A: Cloud Run (serverless)

The repo includes a **Dockerfile** and **scripts/entrypoint_gcs.py** (uses `google-cloud-storage`, not gsutil). At container start, if `PEPMLM_GCS_URI` is set, the entrypoint copies the model from GCS to local storage and sets `PEPMLM_MODEL_PATH` before starting the API. Cold starts will be slower while the model downloads; subsequent requests are fast until the instance scales down.

**2A.1 Build and deploy**

From the project root:

```bash
gcloud run deploy plasmid-optimizer \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 4Gi \
  --timeout 300 \
  --set-env-vars "PEPMLM_GCS_URI=gs://plasmidgo/pepmlm-650m"
```

If the build fails (e.g. out of memory during `pip install`), use the provided **cloudbuild.yaml**, which requests a larger build machine:

```bash
gcloud builds submit --config=cloudbuild.yaml
```

Ensure the Cloud Run service account has **Storage Object Viewer** on your bucket (e.g. `gsutil iam ch serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com:objectViewer gs://plasmidgo`).

**2A.2 Cloud Run limits**

- **Memory**: Set at least 4GB (e.g. `--memory 4Gi`) so the model can load.
- **Timeout**: Increase request timeout if generation is slow (e.g. 300s).
- **Cold starts**: First request after idle will be slow while the model downloads and loads; subsequent requests are fast until the instance is scaled down.

---

### Option B: GCE VM (always-on, fast restarts)

Run the API on a small VM with a **persistent disk** that holds the model. No download on every start.

**2B.1 Create a VM with a data disk (or use the boot disk)**

```bash
# Create a disk that will hold the model (~3GB)
gcloud compute disks create pepmlm-disk --size=10GB --zone=us-central1-a

# Create a VM (e.g. e2-medium or n1-standard-2; use a GPU instance if you have one)
gcloud compute instances create plasmid-optimizer-vm \
  --zone=us-central1-a \
  --machine-type=e2-medium \
  --disk=name=pepmlm-disk,device-name=pepmlm-disk,mode=rw,boot=no \
  --image-family=debian-12 --image-project=debian-cloud \
  --scopes=cloud-platform
```

**2B.2 SSH in, mount the disk, and copy the model from GCS once**

```bash
gcloud compute ssh plasmid-optimizer-vm --zone=us-central1-a
```

On the VM:

```bash
# Format and mount the data disk (if new); use the device name shown by lsblk
sudo mkfs.ext4 -F /dev/sdb   # or the assigned device
sudo mkdir -p /mnt/pepmlm
sudo mount /dev/sdb /mnt/pepmlm
sudo chown $USER /mnt/pepmlm

# Install gcloud/gsutil (or use a service account) and copy model from GCS
gsutil -m cp -r gs://plasmidgo/pepmlm-650m /mnt/pepmlm/
export PEPMLM_MODEL_PATH=/mnt/pepmlm/pepmlm-650m
```

**2B.3 Install the app and run it**

```bash
sudo apt-get update && sudo apt-get install -y python3-pip python3-venv
cd /path/to/plasmid_optimizer   # clone or copy your repo here
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[ml]"
export PEPMLM_MODEL_PATH=/mnt/pepmlm/pepmlm-650m
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Run under a process manager (e.g. systemd) and add the disk mount + `PEPMLM_MODEL_PATH` to your service or profile so it persists across reboots.

**2B.4 Expose the app**

- **Load balancer / HTTPS**: Put the VM behind a load balancer and (optionally) reserve a static IP, or use Cloud Run in front of the VM.
- **Quick test**: `gcloud compute firewall-rules create allow-8000 --allow tcp:8000` and open `http://VM_EXTERNAL_IP:8000`.

---

## 3. Environment variable summary

| Variable | Meaning |
|----------|--------|
| `PEPMLM_MODEL_PATH` | Local directory containing the saved PepMLM tokenizer and model (e.g. after copying from GCS). If set, the app loads from here instead of Hugging Face. |
| `PEPMLM_GCS_URI` | (Optional, for your own entrypoint script.) GCS URI to copy from at startup (e.g. `gs://bucket/pepmlm-650m`). Your script copies this into `PEPMLM_MODEL_PATH`. |

---

## 4. Cost notes

- **GCS**: Storage for the model is a few dollars per month (e.g. ~$0.02/GB in Standard class).
- **Cloud Run**: You pay for CPU/memory and request time; scaling to zero avoids cost when idle. Cold starts re-download the model unless you use a custom cache layer.
- **GCE VM**: You pay for the VM and disk 24/7; good if you want stable latency and no cold starts.

---

## 5. Quick local test with a pre-downloaded model

After exporting the model once:

```bash
python scripts/export_pepmlm_for_gcs.py --output ./pepmlm-650m
export PEPMLM_MODEL_PATH=$(pwd)/pepmlm-650m
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Then open the web UI and use “Generate novel peptides”; the app will load from `./pepmlm-650m` instead of Hugging Face.
