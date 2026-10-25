// 只在 mongo_data volume 第一次初始化時執行（docker-entrypoint-initdb.d）。
// 應用程式不用 root 帳號連線，改用只對業務資料庫有 readWrite 的 app 帳號。
const appUser = process.env.MONGO_APP_USERNAME || 'app';
const appPassword = process.env.MONGO_APP_PASSWORD;
if (!appPassword) throw new Error('MONGO_APP_PASSWORD is required');

db.getSiblingDB('admin').createUser({
  user: appUser,
  pwd: appPassword,
  roles: ['finlab', 'knowledge_base', 'food_ordering', 'investment_db', 'stock_dashboard']
    .map((name) => ({ role: 'readWrite', db: name })),
});
