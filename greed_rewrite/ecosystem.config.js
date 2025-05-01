module.exports = {
    apps: [{
      name: 'greed-rewrite',
      script: '/root/vesta/run.sh',
      interpreter: '/bin/bash',
      cwd: '/root/greed',
      env: {
        NODE_ENV: 'production',
        PYTHONPATH: '/root/greed'
      }
    }]
  };