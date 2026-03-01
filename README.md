### Smart erp ai

smart erp ai

### Installation

Smart ERP AI requires [Frappe Assistant Core](https://github.com/zaalmelahi/Frappe_Assistant_Core) (FAC). The install script fetches both automatically.

**Option 1: Install script (recommended)**

From bench root:
```bash
cd $PATH_TO_YOUR_BENCH
bash apps/smart_erp_ai/install.sh YOUR_SITE
```

Or if you don't have the app yet, download and run:
```bash
cd $PATH_TO_YOUR_BENCH
curl -sSL https://raw.githubusercontent.com/zaalmelahi/Smart-ERP-AI/main/install.sh -o install_smart_erp_ai.sh
bash install_smart_erp_ai.sh YOUR_SITE
```

**Option 2: Manual steps**

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app https://github.com/zaalmelahi/Frappe_Assistant_Core.git
bench get-app https://github.com/zaalmelahi/Smart-ERP-AI.git
bench --site YOUR_SITE install-app smart_erp_ai
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/smart_erp_ai
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### CI

This app can use GitHub Actions for CI. The following workflows are configured:

- CI: Installs this app and runs unit tests on every push to `develop` branch.
- Linters: Runs [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) and [pip-audit](https://pypi.org/project/pip-audit/) on every pull request.


### License

mit
