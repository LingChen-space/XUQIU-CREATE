## Important Notice

Add the following content to hosts if the local environment requires it:

```text
62.234.184.247 autotest.3839.com
```

## CLI Usage

The CLI uses platform subcommands. The common parameters are:

```text
--keyword  Search keyword. Default: 工具
--count    Target cleaned item count. Default: 100
```

### Heybox

```powershell
python main.py heybox --keyword 工具 --count 100 --range 30d --sort default
```

Parameters:

```text
--range  7d | 30d | 180d | 360d
--sort   default | create_date | award_num | comment_num
```

Examples:

```powershell
python main.py heybox --keyword 工具 --count 100 --range 30d --sort default
python main.py heybox --keyword 工具 --count 100 --range 7d --sort create_date
python main.py heybox --keyword 工具 --count 100 --range 360d --sort award_num
```

Output files:

```text
docs/heybox_search_response.json
heybox_search_cleaned.json
```

### TapTap

```powershell
python main.py taptap --keyword 工具 --count 100 --sort default --proxy http://127.0.0.1:17890
```

Parameters:

```text
--sort   default | update_time,desc | commented_time,desc
--proxy  HTTP/HTTPS proxy URL
```

Examples:

```powershell
python main.py taptap --keyword 工具 --count 100 --sort default --proxy http://127.0.0.1:17890
python main.py taptap --keyword 工具 --count 100 --sort update_time,desc --proxy http://127.0.0.1:17890
python main.py taptap --keyword 工具 --count 100 --sort commented_time,desc --proxy http://127.0.0.1:7890
```

Output files:

```text
docs/taptap_search_response.json
taptap_search_cleaned.json
```

### Douyin

Log in first when cookies are missing or verification is required:

```powershell
python main.py douyin --douyin-login
```

Then run search:

```powershell
python main.py douyin --keyword 工具 --count 100 --sort default
```

Parameters:

```text
--sort          default | latest | most_like
--douyin-login  Open douyin.com for manual login and save cookies
--headless      Run Douyin search browser in headless mode
```

Examples:

```powershell
python main.py douyin --douyin-login
python main.py douyin --keyword 工具 --count 100 --sort default
python main.py douyin --keyword 工具 --count 100 --sort latest --headless
python main.py douyin --keyword 工具 --count 100 --sort most_like
```

Output files:

```text
docs/douyin_search_response.json
douyin_search_cleaned.json
```
