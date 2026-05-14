# host_gemma4_vllm

sudo cp deploy/gemma4-e4b.service /etc/systemd/system/gemma4-e4b.service
sudo systemctl daemon-reload
sudo systemctl enable --now gemma4-e4b.service
sudo systemctl status gemma4-e4b.service