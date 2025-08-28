# 💡 Example 

This page summarizes how to deploy a static version of AzTier for demonstration purposes.


## 🐳 Deploy AzTier locally in a container

> [!NOTE]  
> The example directory is located at [example/](../../example/).

### Step 1: Deploy AzTier

In a Linux or Windows terminal (Bash/PowerShell), run the following:

```
git clone https://github.com/emiliensocchi/aztier-deployer.git
```
```
cd aztier-deployer/example/app
```
```
docker run --rm -v "$PWD/aztier:/usr/share/nginx/html/:ro" -p 8080:8080 nginx:latest
```

### Step 2: Browse to the AzTier frontend

In a web browser, navigate to: `http://localhost:8000`.
