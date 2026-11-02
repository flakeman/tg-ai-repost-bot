module.exports = {
  apps: [{
    name: 'tg-ai-repost-bot',
    script: '.venv/bin/python',
    args: '-m src.main',
    cwd: '/root/tg-ai-repost-bot',
    interpreter: 'none',
    autorestart: true,
    watch: false,
    max_memory_restart: '150M',
    env: {
      PYTHONUNBUFFERED: '1'
    }
  }]
};
