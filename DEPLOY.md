# Публикация на GitHub Pages

1. В репозитории откройте **Settings → Pages → Build and deployment** и выберите **Source → GitHub Actions**.
2. Добавьте изменения в коммит и отправьте его в ветку `main`. Если коммит уже на GitHub, запустите **Actions → Deploy to GitHub Pages → Run workflow**.
3. После успешного запуска откройте адрес из **Settings → Pages**. Для сайта проекта это `https://<владелец>.github.io/<репозиторий>/`.

Для предварительной проверки соберите сайт в PowerShell с Node.js 24.

```powershell
npm.cmd ci
npm.cmd run build:pages
python -m http.server 8080 --bind 127.0.0.1 --directory web/dist-pages
```

Откройте адрес `http://127.0.0.1:8080/`. В сборку входят все фотографии и исходный каталог из `schema.sql`. В браузере можно фильтровать каталог, собирать корзину и оформлять демонстрационные продажи. Остатки и история на GitHub Pages хранятся в браузере посетителя.

Для локальной работы с SQLite выполните `npm.cmd run build` и запустите `python app.py` или `java Main.java`. Эта сборка использует API выбранного сервера.
