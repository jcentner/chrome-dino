1. installed miniconda
2. anaconda terminal:

cd ~/Users/jakce/chrome-dino/
- conda --version
- conda update conda -y
- conda create --name chrome-dino -y
- conda activate chrome-dino
- conda info --envs
- conda install -c conda-forge jupyterlab -y

3. opened jupyter

- jupyter-lab chrome-dino.ipynb

4. additional dependencies 

CUDA Toolkit 11.8 (GPU not necessary but why not)

- install CUDA on Windows https://developer.nvidia.com/cuda-toolkit-archive
- conda install pytorch torchvision torchaudio pytorch-cuda=11.8 -c pytorch -c nvidia

Working with Windows for this since my Linux VM has no GPU passthrough
TODO: set up using a python virtual environment rather than miniconda

Google Tesseract-OCR

- install Google Tesseract-OCR: https://github.com/tesseract-ocr/tesseract; https://github.com/UB-Mannheim/tesseract/wiki
- 
