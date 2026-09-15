# 脚本目录

| 目录 | 运行环境 | 用途 |
|------|----------|------|
| [`guest/`](guest/) | Ubuntu 22.04 VM | 编译 openvela / edge_walker |
| [`host/`](host/) | Windows 11 | 烧录、串口冒烟、触摸探测 |
| [`patches/`](patches/) | Ubuntu | 板级补丁（触摸 I2C 等） |
| [`submission/`](submission/) | 任意 | 提交 zip 打包、日志归档 |
| [`archive/`](archive/) | — | 历史一次性脚本（勿用） |

## 常用命令

**Ubuntu 编译主程序：**

```bash
cd ~/openvela
bash contest2026_313_bianyuanxingzhe/scripts/guest/build_ew_main.sh
```

产物拷贝到 HGFS：`/mnt/hgfs/VMware_share/artifacts/nuttx.bin`

**Windows 烧录：**

```powershell
powershell -ExecutionPolicy Bypass -File scripts\host\flash_sf32.ps1 `
  -Port COM7 -Firmware "VMware_share\artifacts\nuttx.bin@0x12010000"
```

**提交打包：**

```bash
python scripts/submission/pack_submission.py
```

VM 交接见 [`docs/协作/UBUNTU_CURSOR_HANDOFF.md`](../docs/协作/UBUNTU_CURSOR_HANDOFF.md)。
