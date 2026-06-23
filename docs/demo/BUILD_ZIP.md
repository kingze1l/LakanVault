# Build the LMS demo zip

From the project root (PowerShell):

```powershell
.\scripts\build_demo_package.ps1
```

This will:

1. Download llama.cpp + Qwen 0.5B into `runtime\` if missing (~450 MB, needs network)
2. Copy demo integrity models into `data\models\`
3. Stage the project into `dist\LakanVault_DEMO\`
4. Create **`dist\LakanVault_DEMO.zip`**

Skip the runtime download if you already have `runtime\`:

```powershell
.\scripts\build_demo_package.ps1 -SkipFetch
```

Upload **`dist/LakanVault_DEMO.zip`** to your LMS.

**Marker instructions:** unzip → double-click **`RUN_DEMO.bat`** → browser opens at http://127.0.0.1:8080
