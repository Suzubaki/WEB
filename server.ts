import express, { Request, Response, NextFunction } from 'express';
import session from 'express-session';
import cookieParser from 'cookie-parser';
import path from 'path';
import { fileURLToPath } from 'url';
import bcrypt from 'bcryptjs';
import ExcelJS from 'exceljs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 3000;

// Configuration & Categories
const DISPOSAL_CATEGORIES: Record<string, string[]> = {
  'падёж': [
    'Патологические роды',
    'Моцерация плода',
    'Травма позвоночного столба',
    'Обширное повреждение мягких тканей',
    'Цирроз',
    'Острая тимпания',
    'Гастроэнтерит',
    'Бронхопневмония',
    'Проводная язва',
    'Перитонит',
    'Травматический ретикулит',
    'Разрыв селезенки',
    'Пневмоторакс',
    'Сальпингит',
    'Диспепсия',
    'Гипотрофия',
    'Разрыв маточной артерии',
    'Разрыв печени',
    'Внутреннее кровотечение',
    'Другое'
  ],
  'выбраковка': [
    'Агалактия',
    'Фримартинизм',
    'Хронический эндомитрит',
    'Параметрит',
    'Фолликулярная киста',
    'Лютеиновая киста',
    'Туберкулез',
    'Другое'
  ],
  'санитарный': [
    'Травма конечностей',
    'Травма позвоночного столба',
    'Стойкая атония преджелудков',
    'Моцерация плода',
    'Патологические роды',
    'Кетоз',
    'Гнойный мастит',
    'Отек',
    'Другое'
  ]
};

// In-Memory Data Models
export interface User {
  id: number;
  username: string;
  password_hash: string;
  user_type: 'admin' | 'farm';
  farm_name?: string | null;
  created_at: string;
}

export interface Cow {
  id: number;
  cow_id: string;
  ear_tag?: string;
  farm_name: string;
  category: string;
  reason: string;
  disposal_date: string;
  lactation?: number;
  weight?: number;
  notes?: string;
  age_group?: string;
  breed?: string;
  milk_yield?: number;
  book_value?: number;
  autopsy_protocol?: string;
  autopsy_vet?: string;
  autopsy_date?: string;
  autopsy_lab_sample?: string;
  created_at: string;
  created_by?: number;
}

// Initial Data Store
let userIdCounter = 1;
let cowIdCounter = 1;

export const economicSettings = {
  meat_price_per_kg: 6.20,
  milk_price_per_kg: 1.18,
  replacement_cost: 2950.00
};

const users: User[] = [
  {
    id: userIdCounter++,
    username: 'admin',
    password_hash: bcrypt.hashSync('admin123', 10),
    user_type: 'admin',
    farm_name: null,
    created_at: '2026-01-01 10:00:00'
  },
  {
    id: userIdCounter++,
    username: 'farm1',
    password_hash: bcrypt.hashSync('farm123', 10),
    user_type: 'farm',
    farm_name: 'МТФ-1 Центральная',
    created_at: '2026-01-01 10:00:00'
  },
  {
    id: userIdCounter++,
    username: 'farm2',
    password_hash: bcrypt.hashSync('farm123', 10),
    user_type: 'farm',
    farm_name: 'МТФ-2 Заречье',
    created_at: '2026-01-01 10:00:00'
  },
  {
    id: userIdCounter++,
    username: 'farm3',
    password_hash: bcrypt.hashSync('farm123', 10),
    user_type: 'farm',
    farm_name: 'МТФ-3 Полесье',
    created_at: '2026-01-01 10:00:00'
  }
];

// Date formatting using local calendar parts
const now = new Date();
function formatDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function getSeedDate(monthOffset: number, dayOfMonth: number): string {
  const targetYear = now.getFullYear();
  const targetMonth = now.getMonth() - monthOffset;
  let safeDay = dayOfMonth;
  if (monthOffset === 0) {
    safeDay = Math.min(dayOfMonth, now.getDate());
    if (safeDay < 1) safeDay = 1;
  }
  const d = new Date(targetYear, targetMonth, safeDay);
  return formatDate(d);
}

const sampleCows: Cow[] = [];

// Seed sample cows spanning current month, previous month, quarter, and year
const sampleSeeds = [
  // Текущий месяц (гарантированно внутри текущего месяца)
  { farm: 'МТФ-1 Центральная', cat: 'падёж', reason: 'Острая тимпания', mOffset: 0, day: 1, tag: 'BY 04 9812401', lact: 3, w: 540, ag: 'Коровы дойного стада', bv: 2400, createdBy: 2 },
  { farm: 'МТФ-1 Центральная', cat: 'выбраковка', reason: 'Гнойный мастит', mOffset: 0, day: 2, tag: 'BY 04 9812402', lact: 4, w: 520, ag: 'Коровы дойного стада', bv: 1800, createdBy: 2 },
  { farm: 'МТФ-2 Заречье', cat: 'падёж', reason: 'Бронхопневмония', mOffset: 0, day: 3, tag: 'BY 04 7715011', lact: 1, w: 68, ag: 'Телята (0–6 мес.)', bv: 380, createdBy: 3 },
  { farm: 'МТФ-2 Заречье', cat: 'санитарный', reason: 'Травма конечностей', mOffset: 0, day: 4, tag: 'BY 04 7715012', lact: 2, w: 510, ag: 'Коровы дойного стада', bv: 2600, createdBy: 3 },
  { farm: 'МТФ-3 Полесье', cat: 'выбраковка', reason: 'Агалактия', mOffset: 0, day: 5, tag: 'BY 04 6614101', lact: 5, w: 560, ag: 'Коровы дойного стада', bv: 1500, createdBy: 4 },
  { farm: 'МТФ-1 Центральная', cat: 'падёж', reason: 'Диспепсия', mOffset: 0, day: 6, tag: 'BY 04 9812403', lact: 0, w: 42, ag: 'Телята (0–6 мес.)', bv: 350, createdBy: 2 },
  { farm: 'МТФ-2 Заречье', cat: 'выбраковка', reason: 'Фолликулярная киста', mOffset: 0, day: 7, tag: 'BY 04 7715013', lact: 3, w: 530, ag: 'Коровы дойного стада', bv: 2200, createdBy: 3 },
  { farm: 'МТФ-3 Полесье', cat: 'санитарный', reason: 'Стойкая атония преджелудков', mOffset: 0, day: 8, tag: 'BY 04 6614102', lact: 3, w: 495, ag: 'Коровы дойного стада', bv: 2100, createdBy: 4 },
  
  // Прошлый месяц (1 месяц назад)
  { farm: 'МТФ-1 Центральная', cat: 'падёж', reason: 'Травматический ретикулит', mOffset: 1, day: 26, tag: 'BY 04 9812390', lact: 2, w: 535, ag: 'Коровы дойного стада', bv: 2500, createdBy: 2 },
  { farm: 'МТФ-1 Центральная', cat: 'выбраковка', reason: 'Хронический эндомитрит', mOffset: 1, day: 22, tag: 'BY 04 9812391', lact: 4, w: 545, ag: 'Коровы дойного стада', bv: 1950, createdBy: 2 },
  { farm: 'МТФ-2 Заречье', cat: 'падёж', reason: 'Перитонит', mOffset: 1, day: 19, tag: 'BY 04 7715001', lact: 3, w: 525, ag: 'Коровы дойного стада', bv: 2400, createdBy: 3 },
  { farm: 'МТФ-2 Заречье', cat: 'санитарный', reason: 'Патологические роды', mOffset: 1, day: 16, tag: 'BY 04 7715002', lact: 2, w: 550, ag: 'Нетели', bv: 2900, createdBy: 3 },
  { farm: 'МТФ-3 Полесье', cat: 'выбраковка', reason: 'Агалактия', mOffset: 1, day: 13, tag: 'BY 04 6614090', lact: 3, w: 490, ag: 'Коровы дойного стада', bv: 2150, createdBy: 4 },
  { farm: 'МТФ-1 Центральная', cat: 'падёж', reason: 'Гастроэнтерит', mOffset: 1, day: 10, tag: 'BY 04 9812380', lact: 1, w: 75, ag: 'Телята (0–6 мес.)', bv: 400, createdBy: 2 },
  { farm: 'МТФ-2 Заречье', cat: 'санитарный', reason: 'Кетоз', mOffset: 1, day: 6, tag: 'BY 04 7715003', lact: 3, w: 515, ag: 'Коровы дойного стада', bv: 2250, createdBy: 3 },
  
  // 2 месяца назад
  { farm: 'МТФ-1 Центральная', cat: 'выбраковка', reason: 'Гнойный мастит', mOffset: 2, day: 25, tag: 'BY 04 9812365', lact: 4, w: 515, ag: 'Коровы дойного стада', bv: 1900, createdBy: 2 },
  { farm: 'МТФ-2 Заречье', cat: 'падёж', reason: 'Острая тимпания', mOffset: 2, day: 18, tag: 'BY 04 7714980', lact: 2, w: 530, ag: 'Коровы дойного стада', bv: 2550, createdBy: 3 },
  { farm: 'МТФ-3 Полесье', cat: 'падёж', reason: 'Цирроз', mOffset: 2, day: 12, tag: 'BY 04 6614070', lact: 5, w: 480, ag: 'Коровы дойного стада', bv: 1400, createdBy: 4 },
  { farm: 'МТФ-1 Центральная', cat: 'санитарный', reason: 'Кетоз', mOffset: 2, day: 7, tag: 'BY 04 9812340', lact: 2, w: 490, ag: 'Коровы сухостойные', bv: 2300, createdBy: 2 },
  
  // 3-11 месяцев назад (формирование годового тренда)
  { farm: 'МТФ-2 Заречье', cat: 'выбраковка', reason: 'Лютеиновая киста', mOffset: 3, day: 20, tag: 'BY 04 7714950', lact: 3, w: 530, ag: 'Коровы дойного стада', bv: 2350, createdBy: 3 },
  { farm: 'МТФ-3 Полесье', cat: 'падёж', reason: 'Бронхопневмония', mOffset: 4, day: 15, tag: 'BY 04 6614050', lact: 1, w: 60, ag: 'Телята (0–6 мес.)', bv: 360, createdBy: 4 },
  { farm: 'МТФ-1 Центральная', cat: 'выбраковка', reason: 'Туберкулез', mOffset: 5, day: 14, tag: 'BY 04 9812310', lact: 4, w: 530, ag: 'Коровы дойного стада', bv: 1800, createdBy: 2 },
  { farm: 'МТФ-2 Заречье', cat: 'падёж', reason: 'Разрыв маточной артерии', mOffset: 6, day: 22, tag: 'BY 04 7714920', lact: 3, w: 550, ag: 'Коровы дойного стада', bv: 2450, createdBy: 3 },
  { farm: 'МТФ-1 Центральная', cat: 'санитарный', reason: 'Травма позвоночного столба', mOffset: 7, day: 11, tag: 'BY 04 9812280', lact: 2, w: 520, ag: 'Коровы дойного стада', bv: 2400, createdBy: 2 },
  { farm: 'МТФ-3 Полесье', cat: 'падёж', reason: 'Диспепсия', mOffset: 8, day: 9, tag: 'BY 04 6614010', lact: 0, w: 38, ag: 'Телята (0–6 мес.)', bv: 340, createdBy: 4 },
  { farm: 'МТФ-2 Заречье', cat: 'выбраковка', reason: 'Агалактия', mOffset: 9, day: 17, tag: 'BY 04 7714880', lact: 4, w: 510, ag: 'Коровы дойного стада', bv: 1750, createdBy: 3 },
  { farm: 'МТФ-1 Центральная', cat: 'падёж', reason: 'Проводная язва', mOffset: 10, day: 8, tag: 'BY 04 9812240', lact: 2, w: 505, ag: 'Коровы дойного стада', bv: 2350, createdBy: 2 },
  { farm: 'МТФ-3 Полесье', cat: 'выбраковка', reason: 'Хронический эндомитрит', mOffset: 11, day: 24, tag: 'BY 04 6613980', lact: 3, w: 525, ag: 'Коровы дойного стада', bv: 2100, createdBy: 4 },
  { farm: 'МТФ-2 Заречье', cat: 'падёж', reason: 'Травматический ретикулит', mOffset: 11, day: 5, tag: 'BY 04 7714820', lact: 3, w: 540, ag: 'Коровы дойного стада', bv: 2400, createdBy: 3 }
];

const farmCounters: Record<string, number> = {};

for (const seed of sampleSeeds) {
  farmCounters[seed.farm] = (farmCounters[seed.farm] || 0) + 1;
  const numStr = String(farmCounters[seed.farm]).padStart(3, '0');
  const dateStr = getSeedDate(seed.mOffset, seed.day);
  sampleCows.push({
    id: cowIdCounter++,
    cow_id: `${seed.farm.split(' ')[0]}-${numStr}`,
    ear_tag: seed.tag,
    farm_name: seed.farm,
    category: seed.cat,
    reason: seed.reason,
    disposal_date: dateStr,
    lactation: seed.lact,
    weight: seed.w,
    age_group: seed.ag,
    breed: 'Черно-пёстрая',
    book_value: seed.bv,
    milk_yield: seed.ag === 'Коровы дойного стада' ? 6200 : 0,
    created_at: `${dateStr} 12:00:00`,
    created_by: seed.createdBy
  });
}

const cows: Cow[] = [...sampleCows];

// Helpers
function generateCowId(farmName: string): string {
  const prefix = `${farmName}-`;
  let maxNum = 0;
  for (const cow of cows) {
    if (cow.farm_name === farmName && cow.cow_id.startsWith(prefix)) {
      const parts = cow.cow_id.split('-');
      const num = parseInt(parts[parts.length - 1], 10);
      if (!isNaN(num) && num > maxNum) {
        maxNum = num;
      }
    }
  }
  const nextNum = maxNum + 1;
  return `${farmName}-${String(nextNum).padStart(3, '0')}`;
}

// App Settings & Middlewares
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(cookieParser());
app.use(express.static(path.join(__dirname, 'public')));
app.use('/static', express.static(path.join(__dirname, 'public')));

declare module 'express-session' {
  interface SessionData {
    user_id?: number;
    username?: string;
    user_type?: 'admin' | 'farm';
    farm_name?: string | null;
    flashMessages?: { category: string; message: string }[];
  }
}

app.use(
  session({
    secret: process.env.SESSION_SECRET || 'dev-secret-key-change-in-production',
    resave: false,
    saveUninitialized: false,
    cookie: { maxAge: 24 * 60 * 60 * 1000 }
  })
);

// Flash Messages and Auto-Session helper middleware
app.use((req: Request, res: Response, next: NextFunction) => {
  if (!req.session.user_id) {
    const adminUser = users.find(u => u.username === 'admin') || users[0];
    if (adminUser) {
      req.session.user_id = adminUser.id;
      req.session.username = adminUser.username;
      req.session.user_type = adminUser.user_type;
      req.session.farm_name = adminUser.farm_name;
    }
  }

  const flash = req.session.flashMessages || [];
  req.session.flashMessages = [];
  res.locals.messages = flash;
  res.locals.session = req.session;
  res.locals.all_app_users = users;
  next();
});

function addFlash(req: Request, message: string, category: 'success' | 'danger' | 'warning' | 'info' = 'info') {
  if (!req.session.flashMessages) {
    req.session.flashMessages = [];
  }
  req.session.flashMessages.push({ message, category });
}

// Auth Middlewares
function loginRequired(req: Request, res: Response, next: NextFunction) {
  if (!req.session.user_id) {
    const adminUser = users.find(u => u.username === 'admin') || users[0];
    if (adminUser) {
      req.session.user_id = adminUser.id;
      req.session.username = adminUser.username;
      req.session.user_type = adminUser.user_type;
      req.session.farm_name = adminUser.farm_name;
      return next();
    }
    addFlash(req, 'Пожалуйста, войдите в систему', 'warning');
    return res.redirect('/login');
  }
  next();
}

function adminRequired(req: Request, res: Response, next: NextFunction) {
  if (!req.session.user_id || req.session.user_type !== 'admin') {
    addFlash(req, 'Доступ запрещен. Требуются права администратора', 'danger');
    return res.redirect('/dashboard');
  }
  next();
}

function classifyPathologySystem(reason: string): string {
  const r = (reason || '').toLowerCase();
  if (r.includes('роды') || r.includes('моцерац') || r.includes('эндометр') || r.includes('кист') || r.includes('яловост') || r.includes('маточн') || r.includes('матк') || r.includes('гинекол')) {
    return 'Акушерство и гинекология';
  } else if (r.includes('мастит') || r.includes('агалакти') || r.includes('вымен') || r.includes('соск')) {
    return 'Болезни вымени (маститы)';
  } else if (r.includes('тимпани') || r.includes('гастро') || r.includes('язв') || r.includes('сычуг') || r.includes('рубец') || r.includes('перитонит') || r.includes('ретикул') || r.includes('атони') || r.includes('печен') || r.includes('цирроз')) {
    return 'Органы пищеварения';
  } else if (r.includes('бронхопневмон') || r.includes('пневмон') || r.includes('легк') || r.includes('отек легких') || r.includes('дыхан')) {
    return 'Органы дыхания';
  } else if (r.includes('диспепси') || r.includes('гипотрофи') || r.includes('колибакт')) {
    return 'Болезни молодняка (диспепсия)';
  } else if (r.includes('конечност') || r.includes('перелом') || r.includes('позвоноч') || r.includes('хромот') || r.includes('копыт') || r.includes('сустав') || r.includes('травм')) {
    return 'Конечности и травматизм';
  } else if (r.includes('кетоз') || r.includes('ацидоз') || r.includes('обмен')) {
    return 'Нарушения обмена веществ';
  } else {
    return 'Прочие заболевания';
  }
}

function getDashboardFullData(userType?: string, farmName?: string | null, period: string = 'this_month', customStart?: string, customEnd?: string) {
  const now = new Date();
  let startDate = '';
  let endDate = formatDate(now);
  let periodTitle = '';

  if (period === 'this_month') {
    const d = new Date(now.getFullYear(), now.getMonth(), 1);
    startDate = formatDate(d);
    periodTitle = `Текущий месяц (${now.toLocaleString('ru-RU', { month: 'long', year: 'numeric' })})`;
  } else if (period === 'last_month') {
    const start = new Date(now.getFullYear(), now.getMonth() - 1, 1);
    const end = new Date(now.getFullYear(), now.getMonth(), 0);
    startDate = formatDate(start);
    endDate = formatDate(end);
    periodTitle = `Прошлый месяц (${start.toLocaleString('ru-RU', { month: 'long', year: 'numeric' })})`;
  } else if (period === 'quarter') {
    const qMonth = Math.floor(now.getMonth() / 3) * 3;
    const start = new Date(now.getFullYear(), qMonth, 1);
    startDate = formatDate(start);
    periodTitle = `Текущий квартал (${Math.floor(now.getMonth() / 3) + 1} кв. ${now.getFullYear()})`;
  } else if (period === 'ytd') {
    startDate = `${now.getFullYear()}-01-01`;
    periodTitle = `С начала ${now.getFullYear()} года (YTD)`;
  } else if (period === 'all') {
    startDate = '2000-01-01';
    periodTitle = 'За всё время учёта';
  } else if (period === 'custom' && customStart && customEnd) {
    startDate = customStart;
    endDate = customEnd;
    periodTitle = `С ${startDate} по ${endDate}`;
  } else {
    const d = new Date(now.getFullYear(), now.getMonth(), 1);
    startDate = formatDate(d);
    periodTitle = 'Текущий месяц';
  }

  // Filter cows
  const relevantCows = cows.filter(c => {
    const farmMatch = (userType === 'admin' && (farmName === 'all' || !farmName)) ? true : c.farm_name === farmName;
    const dateMatch = c.disposal_date >= startDate && c.disposal_date <= endDate;
    return farmMatch && dateMatch;
  });

  const categoryCounts: Record<string, number> = { 'падёж': 0, 'выбраковка': 0, 'санитарный': 0 };
  let totalFinancialLossByn = 0;
  const ageGroupCounts: Record<string, number> = {};
  const pathologySystems: Record<string, number> = {};
  const reasonCounts: Record<string, { category: string, count: number }> = {};
  const farmCounts: Record<string, number> = {};

  const meatPrice = 6.20;
  const milkPrice = 1.18;
  const replacementCost = 2950.00;

  for (const c of relevantCows) {
    categoryCounts[c.category] = (categoryCounts[c.category] || 0) + 1;
    farmCounts[c.farm_name] = (farmCounts[c.farm_name] || 0) + 1;

    const ag = c.age_group || 'Коровы дойного стада';
    ageGroupCounts[ag] = (ageGroupCounts[ag] || 0) + 1;

    const sys = classifyPathologySystem(c.reason);
    pathologySystems[sys] = (pathologySystems[sys] || 0) + 1;

    if (!reasonCounts[c.reason]) {
      reasonCounts[c.reason] = { category: c.category, count: 0 };
    }
    reasonCounts[c.reason].count++;

    // Financial loss
    let w = c.weight || 0;
    let bv = c.book_value || 0;
    const lact = c.lactation || 1;
    if (w <= 0) w = ag.toLowerCase().includes('тел') ? 70 : 520;
    if (bv <= 0) {
      const deprec = Math.max(0.2, 1.0 - (lact - 1) * 0.18);
      bv = replacementCost * deprec;
    }

    if (c.category === 'падёж') {
      totalFinancialLossByn += Math.max(bv, w * meatPrice);
    } else if (c.category === 'санитарный') {
      totalFinancialLossByn += Math.max(0, bv - (w * meatPrice * 0.55));
    } else if (c.category === 'выбраковка') {
      const meatRev = w * meatPrice * 0.90;
      const directDeprec = Math.max(0, bv - meatRev);
      const milkLoss = lact < 4 ? (4 - lact) * 6000 * milkPrice * 0.12 : 0;
      totalFinancialLossByn += (directDeprec + milkLoss);
    }
  }

  const totalDisposals = relevantCows.length;
  const sortedAgeGroups = Object.entries(ageGroupCounts).sort((a, b) => b[1] - a[1]);
  const sortedPathology = Object.entries(pathologySystems).sort((a, b) => b[1] - a[1]);
  const sortedFarms = Object.entries(farmCounts).sort((a, b) => b[1] - a[1]);
  const topReasonsList = Object.entries(reasonCounts)
    .sort((a, b) => b[1].count - a[1].count)
    .slice(0, 8)
    .map(([reason, data]) => ({ reason, category: data.category, count: data.count }));

  // 12 months trend
  const twelveMonthsAgo = new Date();
  twelveMonthsAgo.setMonth(twelveMonthsAgo.getMonth() - 11);
  twelveMonthsAgo.setDate(1);
  const trendMonths: string[] = [];
  for (let i = 0; i < 12; i++) {
    const d = new Date(twelveMonthsAgo.getFullYear(), twelveMonthsAgo.getMonth() + i, 1);
    trendMonths.push(d.toISOString().substring(0, 7));
  }

  const categoryColors: Record<string, string> = {
    'падёж': '#DC2626',
    'выбраковка': '#2563EB',
    'санитарный': '#D97706'
  };

  const trendDatasets = ['падёж', 'выбраковка', 'санитарный'].map(cat => {
    const data = trendMonths.map(m => {
      return cows.filter(c => {
        const farmMatch = (userType === 'admin' && (farmName === 'all' || !farmName)) ? true : c.farm_name === farmName;
        return farmMatch && c.disposal_date.startsWith(m) && c.category === cat;
      }).length;
    });
    const col = categoryColors[cat] || '#64748B';
    return {
      label: cat.charAt(0).toUpperCase() + cat.slice(1),
      data,
      borderColor: col,
      backgroundColor: col + '20',
      fill: true,
      tension: 0.25
    };
  });

  // Calculate previous period for MoM comparison
  let growthPct = 0;
  let prevPeriodCount = 0;
  try {
    const dStart = new Date(startDate);
    const dEnd = new Date(endDate);
    const diffDays = Math.round((dEnd.getTime() - dStart.getTime()) / 86400000) + 1;
    const prevEnd = new Date(dStart.getTime() - 86400000);
    const prevStart = new Date(prevEnd.getTime() - (diffDays - 1) * 86400000);
    const prevStartStr = formatDate(prevStart);
    const prevEndStr = formatDate(prevEnd);

    prevPeriodCount = cows.filter(c => {
      const farmMatch = (userType === 'admin' && (farmName === 'all' || !farmName)) ? true : c.farm_name === farmName;
      return farmMatch && c.disposal_date >= prevStartStr && c.disposal_date <= prevEndStr;
    }).length;

    if (prevPeriodCount > 0) {
      growthPct = Math.round(((totalDisposals - prevPeriodCount) / prevPeriodCount) * 1000) / 10;
    } else {
      growthPct = totalDisposals > 0 ? 100 : 0;
    }
  } catch (e) {
    growthPct = 0;
  }

  const calfDisposals = relevantCows.filter(c => (c.age_group || '').toLowerCase().includes('тел'));
  const calfDeathCount = calfDisposals.filter(c => c.category === 'падёж').length;

  const distinctFarmsList = [...new Set(users.filter(u => u.user_type === 'farm' && u.farm_name).map(u => u.farm_name!))];
  if (distinctFarmsList.length === 0) distinctFarmsList.push('Ферма 1', 'Ферма 2');

  const recentCows = [...relevantCows].sort((a, b) => b.disposal_date.localeCompare(a.disposal_date)).slice(0, 10);

  return {
    period_info: {
      period,
      start_date: startDate,
      end_date: endDate,
      title: periodTitle
    },
    kpi: {
      total_disposals: totalDisposals,
      prev_period_count: prevPeriodCount,
      growth_pct: growthPct,
      death_count: categoryCounts['падёж'],
      culling_count: categoryCounts['выбраковка'],
      sanitary_count: categoryCounts['санитарный'],
      death_rate_pct: totalDisposals > 0 ? Math.round((categoryCounts['падёж'] / totalDisposals) * 1000) / 10 : 0,
      financial_loss_byn: Math.round(totalFinancialLossByn),
      avg_loss_per_cow: totalDisposals > 0 ? Math.round((totalFinancialLossByn / totalDisposals) * 10) / 10 : 0,
      calf_disposals: calfDisposals.length,
      calf_death_count: calfDeathCount,
      all_time_total: cows.filter(c => (userType === 'admin' && (farmName === 'all' || !farmName)) ? true : c.farm_name === farmName).length
    },
    charts: {
      categories: {
        labels: ['Падёж', 'Выбраковка', 'Санитарный брак'],
        data: [categoryCounts['падёж'], categoryCounts['выбраковка'], categoryCounts['санитарный']],
        colors: ['#EF4444', '#3B82F6', '#F59E0B']
      },
      age_groups: {
        labels: sortedAgeGroups.map(x => x[0]),
        data: sortedAgeGroups.map(x => x[1]),
        colors: '#10B981'
      },
      pathology: {
        labels: sortedPathology.map(x => x[0]),
        data: sortedPathology.map(x => x[1]),
        colors: '#6366F1'
      },
      farms: {
        labels: sortedFarms.map(x => x[0]),
        data: sortedFarms.map(x => x[1]),
        colors: '#0284C7'
      },
      trend: {
        labels: trendMonths,
        datasets: trendDatasets
      }
    },
    top_reasons: topReasonsList,
    recent_cows: recentCows,
    all_farms: distinctFarmsList
  };
}

function getAnomalyAlerts(userType?: string, farmName?: string | null) {
  const alerts: { type: string, icon: string, title: string, message: string }[] = [];
  const now = new Date();
  const d7AgoStr = formatDate(new Date(now.getTime() - 7 * 86400000));
  const d14AgoStr = formatDate(new Date(now.getTime() - 14 * 86400000));
  const d30AgoStr = formatDate(new Date(now.getTime() - 30 * 86400000));

  const relevantCows = cows.filter(c => {
    if (userType === 'admin' && (farmName === 'all' || !farmName)) return true;
    return c.farm_name === farmName;
  });

  const last7Deaths = relevantCows.filter(c => c.category === 'падёж' && c.disposal_date >= d7AgoStr).length;
  const prev7Deaths = relevantCows.filter(c => c.category === 'падёж' && c.disposal_date >= d14AgoStr && c.disposal_date < d7AgoStr).length;

  if (last7Deaths > 2 && last7Deaths > prev7Deaths * 1.3) {
    const growth = Math.round(((last7Deaths - prev7Deaths) / Math.max(prev7Deaths, 1)) * 100);
    alerts.push({
      type: 'danger',
      icon: 'bi-exclamation-octagon-fill',
      title: 'Резкий рост падежа скота за последние 7 дней',
      message: `Зафиксировано ${last7Deaths} случаев падежа (+${growth}% к предыдущей неделе). Требуется контроль главного ветврача.`
    });
  }

  // Frequent diagnoses in last 30 days
  const d30Cows = relevantCows.filter(c => c.disposal_date >= d30AgoStr);
  const diagCounts: Record<string, { farm: string, count: number, cat: string }> = {};
  for (const c of d30Cows) {
    const key = `${c.reason}___${c.farm_name}`;
    if (!diagCounts[key]) diagCounts[key] = { farm: c.farm_name, count: 0, cat: c.category };
    diagCounts[key].count++;
  }

  for (const [key, item] of Object.entries(diagCounts)) {
    if (item.count >= 2) {
      const reason = key.split('___')[0];
      alerts.push({
        type: 'warning',
        icon: 'bi-exclamation-triangle-fill',
        title: `Повторяющаяся патология: ${reason}`,
        message: `Подразделение «${item.farm}»: за 30 дней зафиксировано ${item.count} случаев (${item.cat}). Проверьте рацион и подстилочный материал.`
      });
      break;
    }
  }

  // Calf mortality
  const calfDeaths30 = d30Cows.filter(c => c.category === 'падёж' && (c.age_group || '').toLowerCase().includes('тел')).length;
  if (calfDeaths30 >= 2) {
    alerts.push({
      type: 'info',
      icon: 'bi-info-circle-fill',
      title: `Падёж телят (0-6 мес.): ${calfDeaths30} гол. за 30 дней`,
      message: 'Рекомендуется проверить своевременность выпойки молозива и микроклимат в секции профилактория.'
    });
  }

  return alerts;
}

// Backward compatibility helpers
function getStatisticsData(userType?: string, farmName?: string | null) {
  const full = getDashboardFullData(userType, farmName, 'all');
  const categories: Record<string, number> = {};
  full.charts.categories.labels.forEach((l, i) => { categories[l] = full.charts.categories.data[i]; });
  const farms: Record<string, number> = {};
  full.charts.farms.labels.forEach((l, i) => { farms[l] = full.charts.farms.data[i]; });
  return {
    categories,
    farms,
    monthly_data: {},
    overview: {
      total_cows: full.kpi.total_disposals,
      total_farms: full.all_farms.length,
      avg_per_farm: full.kpi.total_disposals / Math.max(full.all_farms.length, 1)
    }
  };
}

function prepareChartData(statsData: any) {
  return {
    categories_chart: { labels: Object.keys(statsData.categories), data: Object.values(statsData.categories) },
    farms_chart: { labels: Object.keys(statsData.farms), data: Object.values(statsData.farms) },
    line_chart: { labels: [], datasets: [] },
    overview: statsData.overview
  };
}

function getDashboardStats(userType?: string, farmName?: string | null) {
  const full = getDashboardFullData(userType, farmName, 'this_month');
  return {
    recent_stats: cows.filter(c => c.disposal_date >= formatDate(new Date(Date.now() - 30 * 86400000))),
    total_cows: full.kpi.all_time_total,
    total_farms: full.all_farms.length,
    your_farm_total: full.kpi.total_disposals
  };
}

function getUserStatistics() {
  const userTypes: Record<string, number> = {};
  for (const u of users) {
    userTypes[u.user_type] = (userTypes[u.user_type] || 0) + 1;
  }

  const userActivity = users.map(u => {
    const userCows = cows.filter(c => c.created_by === u.id || (u.user_type === 'farm' && c.farm_name === u.farm_name));
    let lastActivity = 'Нет данных';
    if (userCows.length > 0) {
      const sorted = [...userCows].sort((a, b) => b.disposal_date.localeCompare(a.disposal_date));
      lastActivity = sorted[0].disposal_date;
    }
    return {
      username: u.username,
      user_type: u.user_type,
      farm_name: u.farm_name || '-',
      cows_count: userCows.length,
      last_activity: lastActivity
    };
  });

  return {
    user_types: userTypes,
    user_activity: userActivity
  };
}

// ----------------- ROUTES -----------------

// Index -> redirect to dashboard
app.get('/', (req: Request, res: Response) => {
  res.redirect('/dashboard');
});

// Quick Switch User (Demo helper)
app.get('/switch_user/:username', (req: Request, res: Response) => {
  const target = users.find(u => u.username === req.params.username);
  if (target) {
    req.session.user_id = target.id;
    req.session.username = target.username;
    req.session.user_type = target.user_type;
    req.session.farm_name = target.farm_name;
    addFlash(req, `Переключено на пользователя: ${target.username} (${target.farm_name || 'Администратор'})`, 'success');
  }
  const referer = req.headers.referer || '/dashboard';
  res.redirect(referer);
});

// Login
app.get('/login', (req: Request, res: Response) => {
  if (req.session.user_id) {
    return res.redirect('/dashboard');
  }
  res.render('login');
});

app.post('/login', (req: Request, res: Response) => {
  const { username, password } = req.body;
  const user = users.find(u => u.username === username);

  if (user && bcrypt.compareSync(password, user.password_hash)) {
    req.session.user_id = user.id;
    req.session.username = user.username;
    req.session.user_type = user.user_type;
    req.session.farm_name = user.farm_name;
    addFlash(req, 'Вход выполнен успешно', 'success');
    return res.redirect('/dashboard');
  }

  addFlash(req, 'Неверное имя пользователя или пароль', 'danger');
  res.render('login');
});

// Logout
app.get('/logout', (req: Request, res: Response) => {
  req.session.destroy(() => {
    res.redirect('/login');
  });
});

// Register (Admin only)
app.get('/register', loginRequired, adminRequired, (req: Request, res: Response) => {
  res.render('register');
});

app.post('/register', loginRequired, adminRequired, (req: Request, res: Response) => {
  const { username, password, user_type, farm_name } = req.body;
  if (users.some(u => u.username === username)) {
    addFlash(req, 'Имя пользователя уже занято', 'danger');
    return res.render('register');
  }

  users.push({
    id: userIdCounter++,
    username,
    password_hash: bcrypt.hashSync(password, 10),
    user_type: user_type as 'admin' | 'farm',
    farm_name: user_type === 'farm' ? farm_name : null,
    created_at: formatDate(new Date()) + ' ' + new Date().toTimeString().split(' ')[0]
  });

  addFlash(req, 'Регистрация успешна. Новый пользователь создан.', 'success');
  res.redirect('/user_management');
});

// User Management (Admin only)
app.get('/user_management', loginRequired, adminRequired, (req: Request, res: Response) => {
  res.render('user_management', { users });
});

// Edit User
app.get('/edit_user/:id', loginRequired, adminRequired, (req: Request, res: Response) => {
  const userId = parseInt(String(req.params.id), 10);
  const user = users.find(u => u.id === userId);
  if (!user) {
    addFlash(req, 'Пользователь не найден', 'danger');
    return res.redirect('/user_management');
  }
  res.render('edit_user', { user });
});

app.post('/edit_user/:id', loginRequired, adminRequired, (req: Request, res: Response) => {
  const userId = parseInt(String(req.params.id), 10);
  const user = users.find(u => u.id === userId);
  if (!user) {
    addFlash(req, 'Пользователь не найден', 'danger');
    return res.redirect('/user_management');
  }

  const { username, password, user_type, farm_name } = req.body;

  if (users.some(u => u.username === username && u.id !== userId)) {
    addFlash(req, 'Имя пользователя уже занято', 'danger');
    return res.render('edit_user', { user });
  }

  user.username = username;
  if (password && password.trim() !== '') {
    user.password_hash = bcrypt.hashSync(password, 10);
  }
  user.user_type = user_type;
  user.farm_name = user_type === 'farm' ? farm_name : null;

  addFlash(req, 'Данные пользователя успешно обновлены', 'success');
  res.redirect('/user_management');
});

// Delete User
app.post('/delete_user/:id', loginRequired, adminRequired, (req: Request, res: Response) => {
  const userId = parseInt(String(req.params.id), 10);
  if (userId === req.session.user_id) {
    addFlash(req, 'Вы не можете удалить свою собственную учетную запись', 'danger');
    return res.redirect('/user_management');
  }

  const index = users.findIndex(u => u.id === userId);
  if (index !== -1) {
    const deletedUser = users[index];
    users.splice(index, 1);

    if (deletedUser.user_type === 'farm' && deletedUser.farm_name) {
      const initialCount = cows.length;
      for (let i = cows.length - 1; i >= 0; i--) {
        if (cows[i].farm_name === deletedUser.farm_name) {
          cows.splice(i, 1);
        }
      }
      addFlash(req, `Пользователь ${deletedUser.username} успешно удален`, 'success');
      addFlash(req, `Также удалены все записи о коровах фермы "${deletedUser.farm_name}"`, 'info');
    } else {
      addFlash(req, `Пользователь ${deletedUser.username} успешно удален`, 'success');
    }
  } else {
    addFlash(req, 'Пользователь не найден', 'danger');
  }

  res.redirect('/user_management');
});

// Dashboard
app.get('/dashboard', loginRequired, (req: Request, res: Response) => {
  const userType = req.session.user_type;
  const farmName = req.session.farm_name;

  const period = (req.query.period as string) || 'this_month';
  const customStart = req.query.custom_start as string;
  const customEnd = req.query.custom_end as string;

  let selectedFarm = farmName;
  if (userType === 'admin') {
    selectedFarm = (req.query.farm as string) || 'all';
  }

  const dashboardData = getDashboardFullData(
    userType,
    selectedFarm,
    period,
    customStart,
    customEnd
  );
  const alerts = getAnomalyAlerts(userType, selectedFarm);
  const userStatsData = userType === 'admin' ? getUserStatistics() : null;
  const statsData = getStatisticsData(userType, farmName);
  const chartData = prepareChartData(statsData);
  const dashboardStats = getDashboardStats(userType, farmName);

  res.render('dashboard', {
    user_type: userType,
    farm_name: farmName,
    selected_farm: selectedFarm,
    d: dashboardData,
    alerts: alerts,
    user_stats_data: userStatsData,
    chart_data: chartData,
    dashboard_stats: dashboardStats
  });
});

// Economics Dashboard (BYN damage calculation)
app.get('/economics', loginRequired, (req: Request, res: Response) => {
  const userType = req.session.user_type;
  const farmName = req.session.farm_name;

  const now = new Date();
  const startDate = (req.query.start_date as string) || formatDate(new Date(now.getFullYear(), now.getMonth(), 1));
  const endDate = (req.query.end_date as string) || formatDate(now);
  let selectedFarm = farmName;
  if (userType === 'admin') {
    selectedFarm = (req.query.farm_name as string) || 'all';
  }

  const relevantCows = cows.filter(c => {
    const farmMatch = (userType === 'admin' && (selectedFarm === 'all' || !selectedFarm)) ? true : c.farm_name === selectedFarm;
    const dateMatch = c.disposal_date >= startDate && c.disposal_date <= endDate;
    return farmMatch && dateMatch;
  });

  const meatPrice = economicSettings.meat_price_per_kg;
  const milkPrice = economicSettings.milk_price_per_kg;
  const replacementCost = economicSettings.replacement_cost;

  let totalLossByn = 0;
  const byCategoryLoss: Record<string, number> = { 'падёж': 0, 'выбраковка': 0, 'санитарный': 0 };
  const byCategoryHeads: Record<string, number> = { 'падёж': 0, 'выбраковка': 0, 'санитарный': 0 };
  const reasonLossMap: Record<string, { category: string; heads: number; loss_byn: number }> = {};

  for (const c of relevantCows) {
    byCategoryHeads[c.category] = (byCategoryHeads[c.category] || 0) + 1;
    let w = c.weight || 0;
    let bv = c.book_value || 0;
    const lact = c.lactation || 1;
    const ag = c.age_group || 'Коровы дойного стада';
    if (w <= 0) w = ag.toLowerCase().includes('тел') ? 70 : 520;
    if (bv <= 0) {
      const deprec = Math.max(0.2, 1.0 - (lact - 1) * 0.18);
      bv = replacementCost * deprec;
    }

    let loss = 0;
    if (c.category === 'падёж') {
      loss = Math.max(bv, w * meatPrice);
    } else if (c.category === 'санитарный') {
      loss = Math.max(0, bv - (w * meatPrice * 0.55));
    } else if (c.category === 'выбраковка') {
      const meatRev = w * meatPrice * 0.90;
      const directDeprec = Math.max(0, bv - meatRev);
      const milkLoss = lact < 4 ? (4 - lact) * 6000 * milkPrice * 0.12 : 0;
      loss = directDeprec + milkLoss;
    }

    totalLossByn += loss;
    byCategoryLoss[c.category] = (byCategoryLoss[c.category] || 0) + loss;

    if (!reasonLossMap[c.reason]) {
      reasonLossMap[c.reason] = { category: c.category, heads: 0, loss_byn: 0 };
    }
    reasonLossMap[c.reason].heads++;
    reasonLossMap[c.reason].loss_byn += loss;
  }

  const topLossReasons = Object.entries(reasonLossMap)
    .sort((a, b) => b[1].loss_byn - a[1].loss_byn)
    .slice(0, 10)
    .map(([reason, r]) => ({ reason, category: r.category, heads: r.heads, loss_byn: r.loss_byn }));

  const distinctFarms = [...new Set(users.filter(u => u.user_type === 'farm' && u.farm_name).map(u => u.farm_name!))];
  for (const c of cows) {
    if (c.farm_name && !distinctFarms.includes(c.farm_name)) distinctFarms.push(c.farm_name);
  }
  distinctFarms.sort();

  res.render('economics', {
    user_type: userType,
    farm_name: selectedFarm,
    start_date: startDate,
    end_date: endDate,
    farms: distinctFarms,
    settings: economicSettings,
    data: {
      total_loss_byn: totalLossByn,
      total_head_count: relevantCows.length,
      avg_loss_per_head: relevantCows.length > 0 ? totalLossByn / relevantCows.length : 0,
      by_category_loss: byCategoryLoss,
      by_category_heads: byCategoryHeads,
      top_loss_reasons: topLossReasons
    }
  });
});

app.post('/api/save_economic_settings', loginRequired, adminRequired, (req: Request, res: Response) => {
  const { meat_price_per_kg, milk_price_per_kg, replacement_cost } = req.body;
  if (meat_price_per_kg) economicSettings.meat_price_per_kg = parseFloat(meat_price_per_kg) || 6.20;
  if (milk_price_per_kg) economicSettings.milk_price_per_kg = parseFloat(milk_price_per_kg) || 1.18;
  if (replacement_cost) economicSettings.replacement_cost = parseFloat(replacement_cost) || 2950.00;
  addFlash(req, 'Экономические нормативы успешно сохранены', 'success');
  res.redirect('/economics');
});

// Bulk Delete Cows
app.post(['/bulk_delete_cows', '/delete_multiple_cows'], loginRequired, (req: Request, res: Response) => {
  const userType = req.session.user_type;
  const farmName = req.session.farm_name;

  if (userType === 'admin') {
    return res.status(403).json({ error: 'Администраторы не могут удалять записи' });
  }

  const rawIds = req.body.cow_ids || req.body.ids || [];
  const idsToDelete = (Array.isArray(rawIds) ? rawIds : [rawIds]).map((id: any) => parseInt(String(id), 10));

  let deletedCount = 0;
  for (let i = cows.length - 1; i >= 0; i--) {
    if (idsToDelete.includes(cows[i].id) && cows[i].farm_name === farmName) {
      cows.splice(i, 1);
      deletedCount++;
    }
  }

  return res.json({ success: true, deleted_count: deletedCount, message: `Удалено ${deletedCount} записей` });
});

// View Cows
app.get('/cows', loginRequired, (req: Request, res: Response) => {
  const userType = req.session.user_type;
  const farmName = req.session.farm_name;

  let filteredCows = cows;
  if (userType !== 'admin') {
    filteredCows = cows.filter(c => c.farm_name === farmName);
  }

  // Sort descending by disposal_date
  filteredCows = [...filteredCows].sort((a, b) => b.disposal_date.localeCompare(a.disposal_date));

  res.render('view_cows', {
    cows: filteredCows,
    user_type: userType
  });
});

// Add Single Cow
app.get('/add_cow', loginRequired, (req: Request, res: Response) => {
  if (req.session.user_type === 'admin') {
    addFlash(req, 'Администраторы не могут добавлять коров. Используйте просмотр и отчёты.', 'warning');
    return res.redirect('/dashboard');
  }

  res.render('add_cow', {
    categories: DISPOSAL_CATEGORIES,
    user_type: req.session.user_type,
    farm_name: req.session.farm_name
  });
});

app.post('/add_cow', loginRequired, (req: Request, res: Response) => {
  if (req.session.user_type === 'admin') {
    addFlash(req, 'Администраторы не могут добавлять коров.', 'warning');
    return res.redirect('/dashboard');
  }

  const farmName = req.session.farm_name || 'Ферма';
  const { category, reason, disposal_date } = req.body;

  if (!category || !reason || !disposal_date) {
    addFlash(req, 'Заполните все поля', 'danger');
    return res.redirect('/add_cow');
  }

  const todayStr = formatDate(new Date());
  if (disposal_date > todayStr) {
    addFlash(req, 'Дата выбытия не может быть позже сегодняшнего дня', 'danger');
    return res.redirect('/add_cow');
  }

  const cowId = generateCowId(farmName);
  cows.push({
    id: cowIdCounter++,
    cow_id: cowId,
    farm_name: farmName,
    category,
    reason,
    disposal_date,
    created_at: formatDate(new Date()) + ' ' + new Date().toTimeString().split(' ')[0],
    created_by: req.session.user_id
  });

  addFlash(req, `Корова успешно добавлена с ID: ${cowId}`, 'success');
  res.redirect('/cows');
});

// Dynamic Add Cows
app.get('/add_cows_dynamic', loginRequired, (req: Request, res: Response) => {
  if (req.session.user_type === 'admin') {
    addFlash(req, 'Администраторы не могут добавлять коров. Используйте просмотр и отчёты.', 'warning');
    return res.redirect('/dashboard');
  }

  res.render('add_cows_dynamic', {
    categories: DISPOSAL_CATEGORIES,
    user_type: req.session.user_type,
    farm_name: req.session.farm_name,
    today: formatDate(new Date())
  });
});

// Add Multiple Cows (supports JSON POST and Form POST)
app.get('/add_multiple_cows', loginRequired, (req: Request, res: Response) => {
  if (req.session.user_type === 'admin') {
    addFlash(req, 'Администраторы не могут добавлять коров.', 'warning');
    return res.redirect('/dashboard');
  }

  res.render('add_multiple_cows', {
    categories: DISPOSAL_CATEGORIES,
    user_type: req.session.user_type,
    farm_name: req.session.farm_name
  });
});

app.post('/add_multiple_cows', loginRequired, (req: Request, res: Response) => {
  if (req.session.user_type === 'admin') {
    if (req.xhr || req.is('json')) {
      return res.status(403).json({ error: 'Администраторы не могут добавлять коров' });
    }
    addFlash(req, 'Администраторы не могут добавлять коров.', 'warning');
    return res.redirect('/dashboard');
  }

  const farmName = req.session.farm_name || 'Ферма';
  let cowsData: any[] = [];

  if (req.is('json') && req.body && Array.isArray(req.body.cows_data)) {
    cowsData = req.body.cows_data;
  } else if (req.body.cows_data) {
    try {
      cowsData = JSON.parse(req.body.cows_data);
    } catch {
      if (req.xhr || req.is('json')) {
        return res.status(400).json({ error: 'Неверный формат JSON' });
      }
      addFlash(req, 'Неверный формат данных. Используйте JSON', 'danger');
      return res.redirect('/add_multiple_cows');
    }
  }

  const todayStr = formatDate(new Date());
  let addedCount = 0;
  let errorCount = 0;

  for (const item of cowsData) {
    if (item.category && item.reason && item.disposal_date) {
      if (item.disposal_date > todayStr) {
        errorCount++;
        continue;
      }
      const cowId = generateCowId(farmName);
      cows.push({
        id: cowIdCounter++,
        cow_id: cowId,
        farm_name: farmName,
        category: item.category,
        reason: item.reason,
        disposal_date: item.disposal_date,
        created_at: formatDate(new Date()) + ' ' + new Date().toTimeString().split(' ')[0],
        created_by: req.session.user_id
      });
      addedCount++;
    } else {
      errorCount++;
    }
  }

  if (req.xhr || req.is('json')) {
    return res.json({ success: true, added_count: addedCount, error_count: errorCount });
  }

  if (addedCount > 0) {
    addFlash(req, `Добавлено ${addedCount} коров с автоматически сгенерированными ID`, 'success');
  }
  if (errorCount > 0) {
    addFlash(req, `${errorCount} записей не добавлено (дата выбытия позже сегодняшнего дня или не все поля)`, 'warning');
  }

  res.redirect('/cows');
});

// Delete Cow
app.post('/delete_cow/:id', loginRequired, (req: Request, res: Response) => {
  const userType = req.session.user_type;
  const farmName = req.session.farm_name;

  if (userType === 'admin') {
    if (req.xhr || req.is('json')) {
      return res.status(403).json({ error: 'Администраторы не могут удалять записи' });
    }
    addFlash(req, 'Администраторы не могут удалять записи о коровах.', 'warning');
    return res.redirect('/cows');
  }

  const cowId = parseInt(String(req.params.id), 10);
  const index = cows.findIndex(c => c.id === cowId && c.farm_name === farmName);

  if (index === -1) {
    if (req.xhr || req.is('json')) {
      return res.status(404).json({ error: 'Запись не найдена или нет доступа' });
    }
    addFlash(req, 'Запись не найдена или вы не имеете прав на её удаление.', 'danger');
    return res.redirect('/cows');
  }

  const deletedCow = cows[index];
  cows.splice(index, 1);

  if (req.xhr || req.is('json')) {
    return res.json({ success: true, message: `Запись ${deletedCow.cow_id} удалена` });
  }

  addFlash(req, `Запись о корове с ID ${deletedCow.cow_id} успешно удалена.`, 'success');
  res.redirect('/cows');
});

// Reports Page
app.get('/reports', loginRequired, (req: Request, res: Response) => {
  res.render('reports', { user_type: req.session.user_type });
});

// Generate Report
app.post('/generate_report', loginRequired, async (req: Request, res: Response) => {
  const { report_type, format, start_date, end_date, farm_filter, report_category } = req.body;
  const userType = req.session.user_type;
  const userFarm = req.session.farm_name;

  let filteredCows = cows.filter(c => {
    const inDateRange = c.disposal_date >= start_date && c.disposal_date <= end_date;
    if (!inDateRange) return false;

    if (userType === 'farm') {
      return c.farm_name === userFarm;
    }

    if (farm_filter && farm_filter !== 'all') {
      return c.farm_name === farm_filter;
    }

    return true;
  });

  filteredCows.sort((a, b) => a.farm_name.localeCompare(b.farm_name) || a.disposal_date.localeCompare(b.disposal_date));

  if (filteredCows.length === 0) {
    addFlash(req, 'Нет данных для выбранного периода', 'warning');
    return res.redirect('/reports');
  }

  // 1. CSV Format
  if (format === 'csv') {
    let csvContent = 'ID,Ферма,Категория,Причина,Дата\n';
    for (const row of filteredCows) {
      csvContent += `"${row.cow_id}","${row.farm_name}","${row.category}","${row.reason}","${row.disposal_date}"\n`;
    }
    const filename = `данные_${start_date}_по_${end_date}.csv`;
    res.setHeader('Content-Type', 'text/csv; charset=utf-8');
    res.setHeader('Content-Disposition', `attachment; filename="${encodeURIComponent(filename)}"`);
    return res.send('\uFEFF' + csvContent); // Add UTF-8 BOM for Excel compatibility
  }

  // 2. HTML Preview Format
  if (format === 'preview') {
    const summary = {
      total_cows: filteredCows.length,
      by_category: {} as Record<string, number>,
      by_reason: {} as Record<string, number>,
      by_farm: {} as Record<string, number>
    };

    for (const c of filteredCows) {
      summary.by_category[c.category] = (summary.by_category[c.category] || 0) + 1;
      summary.by_reason[c.reason] = (summary.by_reason[c.reason] || 0) + 1;
      summary.by_farm[c.farm_name] = (summary.by_farm[c.farm_name] || 0) + 1;
    }

    return res.render('report_preview', {
      data: filteredCows,
      summary,
      start_date,
      end_date,
      farm_filter: farm_filter || userFarm
    });
  }

  // 3. Excel Format (.xlsx)
  const workbook = new ExcelJS.Workbook();
  workbook.creator = 'Система учёта выбытия скота';
  workbook.created = new Date();

  if (report_type === 'matrix') {
    const category = report_category || 'падёж';
    const subcategories = DISPOSAL_CATEGORIES[category] || [];
    const worksheet = workbook.addWorksheet(`Матрица ${category}`);

    // Title
    worksheet.mergeCells('A1:H1');
    const titleCell = worksheet.getCell('A1');
    titleCell.value = 'ОТЧЁТ ПО ВЫБЫТИЮ СКОТА';
    titleCell.font = { name: 'Times New Roman', size: 14, bold: true };
    titleCell.alignment = { horizontal: 'center', vertical: 'middle' };

    worksheet.mergeCells('A2:H2');
    const catCell = worksheet.getCell('A2');
    catCell.value = `Категория: ${category.toUpperCase()}`;
    catCell.font = { bold: true, size: 12 };
    catCell.alignment = { horizontal: 'center', vertical: 'middle' };

    worksheet.mergeCells('A3:H3');
    const dateCell = worksheet.getCell('A3');
    dateCell.value = `Период: с ${start_date} по ${end_date}`;
    dateCell.alignment = { horizontal: 'center', vertical: 'middle' };

    // Get distinct farms in the filtered dataset
    const farms = [...new Set(filteredCows.map(c => c.farm_name))].sort();

    // Table Header Row 6
    const headerRow = worksheet.getRow(6);
    headerRow.getCell(1).value = 'ПРИЧИНЫ ВЫБЫТИЯ';
    headerRow.getCell(1).font = { bold: true };
    headerRow.getCell(1).fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFCCCCCC' } };
    headerRow.getCell(1).alignment = { horizontal: 'center', vertical: 'middle' };

    farms.forEach((farm, idx) => {
      const cell = headerRow.getCell(idx + 2);
      cell.value = farm;
      cell.font = { bold: true };
      cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFCCCCCC' } };
      cell.alignment = { horizontal: 'center', vertical: 'middle' };
    });

    const totalColIdx = farms.length + 2;
    const totalHeaderCell = headerRow.getCell(totalColIdx);
    totalHeaderCell.value = 'ИТОГО';
    totalHeaderCell.font = { bold: true };
    totalHeaderCell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFFF9999' } };
    totalHeaderCell.alignment = { horizontal: 'center', vertical: 'middle' };

    let currentRow = 7;
    for (const subcategory of subcategories) {
      const row = worksheet.getRow(currentRow);
      row.getCell(1).value = subcategory;

      let rowTotal = 0;
      farms.forEach((farm, idx) => {
        const count = filteredCows.filter(
          c => c.farm_name === farm && c.category === category && c.reason === subcategory
        ).length;
        const cell = row.getCell(idx + 2);
        cell.value = count;
        cell.alignment = { horizontal: 'center', vertical: 'middle' };
        rowTotal += count;
      });

      const totalCell = row.getCell(totalColIdx);
      totalCell.value = rowTotal;
      totalCell.font = { bold: true };
      totalCell.alignment = { horizontal: 'center', vertical: 'middle' };
      currentRow++;
    }

    // Totals row
    const summaryRow = worksheet.getRow(currentRow);
    summaryRow.getCell(1).value = 'ИТОГО';
    summaryRow.getCell(1).font = { bold: true };
    summaryRow.getCell(1).fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFFF9999' } };

    let grandTotal = 0;
    farms.forEach((farm, idx) => {
      const count = filteredCows.filter(c => c.farm_name === farm && c.category === category).length;
      const cell = summaryRow.getCell(idx + 2);
      cell.value = count;
      cell.font = { bold: true };
      cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFFF9999' } };
      cell.alignment = { horizontal: 'center', vertical: 'middle' };
      grandTotal += count;
    });

    const grandTotalCell = summaryRow.getCell(totalColIdx);
    grandTotalCell.value = grandTotal;
    grandTotalCell.font = { bold: true };
    grandTotalCell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFFF9999' } };
    grandTotalCell.alignment = { horizontal: 'center', vertical: 'middle' };

    worksheet.getColumn(1).width = 40;
    for (let c = 2; c <= totalColIdx; c++) {
      worksheet.getColumn(c).width = 16;
    }

    const filename = `матричный_отчет_${category}_${start_date}_по_${end_date}.xlsx`;
    res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
    res.setHeader('Content-Disposition', `attachment; filename="${encodeURIComponent(filename)}"`);
    await workbook.xlsx.write(res);
    return res.end();
  }

  // Structured / Simple Excel Report
  const worksheet = workbook.addWorksheet(report_type === 'structured' ? 'Сводный отчёт' : 'Данные');

  if (report_type === 'structured') {
    worksheet.mergeCells('A1:E1');
    const headerCell = worksheet.getCell('A1');
    headerCell.value = 'СВОДНЫЙ ОТЧЁТ ПО ВЫБЫТИЮ СКОТА';
    headerCell.font = { bold: true, size: 14 };
    headerCell.alignment = { horizontal: 'center', vertical: 'middle' };

    worksheet.mergeCells('A2:E2');
    const subCell = worksheet.getCell('A2');
    subCell.value = `Период: ${start_date} — ${end_date}`;
    subCell.alignment = { horizontal: 'center', vertical: 'middle' };

    worksheet.getRow(4).values = ['ID коровы', 'Ферма', 'Категория', 'Причина выбытия', 'Дата выбытия'];
    worksheet.getRow(4).font = { bold: true, color: { argb: 'FFFFFFFF' } };
    worksheet.getRow(4).fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF007BFF' } };

    filteredCows.forEach((cow, i) => {
      const row = worksheet.addRow([cow.cow_id, cow.farm_name, cow.category, cow.reason, cow.disposal_date]);
      if (i % 2 === 1) {
        row.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFF2F2F2' } };
      }
    });

    worksheet.columns = [
      { width: 18 },
      { width: 20 },
      { width: 18 },
      { width: 35 },
      { width: 16 }
    ];

    const filename = `структурированный_отчет_${start_date}_по_${end_date}.xlsx`;
    res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
    res.setHeader('Content-Disposition', `attachment; filename="${encodeURIComponent(filename)}"`);
    await workbook.xlsx.write(res);
    return res.end();
  } else {
    // Simple report
    worksheet.addRow(['ID', 'Ферма', 'Категория', 'Причина', 'Дата']);
    worksheet.getRow(1).font = { bold: true };
    for (const cow of filteredCows) {
      worksheet.addRow([cow.cow_id, cow.farm_name, cow.category, cow.reason, cow.disposal_date]);
    }

    worksheet.columns = [
      { width: 18 },
      { width: 20 },
      { width: 18 },
      { width: 35 },
      { width: 16 }
    ];

    const filename = `простые_данные_${start_date}_по_${end_date}.xlsx`;
    res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
    res.setHeader('Content-Disposition', `attachment; filename="${encodeURIComponent(filename)}"`);
    await workbook.xlsx.write(res);
    return res.end();
  }
});

// Generate Original Template Excel
app.post('/generate_original_excel', loginRequired, adminRequired, async (req: Request, res: Response) => {
  const workbook = new ExcelJS.Workbook();
  const worksheet = workbook.addWorksheet('Выбытие скота Сводка');

  worksheet.mergeCells('A1:G1');
  const titleCell = worksheet.getCell('A1');
  titleCell.value = 'ОФИЦИАЛЬНАЯ СВОДКА ВЫБЫТИЯ СКОТА';
  titleCell.font = { bold: true, size: 14 };
  titleCell.alignment = { horizontal: 'center' };

  worksheet.getRow(3).values = ['Ферма', 'Падёж (гол.)', 'Выбраковка (гол.)', 'Санитарный брак (гол.)', 'Пало, всего (гол.)'];
  worksheet.getRow(3).font = { bold: true, color: { argb: 'FFFFFFFF' } };
  worksheet.getRow(3).fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFDC3545' } };

  const farms = [...new Set(users.filter(u => u.user_type === 'farm' && u.farm_name).map(u => u.farm_name!))];
  if (farms.length === 0) {
    farms.push('Ферма 1', 'Ферма 2');
  }

  for (const farm of farms) {
    const padezh = cows.filter(c => c.farm_name === farm && c.category === 'падёж').length;
    const vybrakovka = cows.filter(c => c.farm_name === farm && c.category === 'выбраковка').length;
    const sanitarniy = cows.filter(c => c.farm_name === farm && c.category === 'санитарный').length;
    const total = padezh + vybrakovka + sanitarniy;
    worksheet.addRow([farm, padezh, vybrakovka, sanitarniy, total]);
  }

  worksheet.columns = [
    { width: 25 },
    { width: 18 },
    { width: 22 },
    { width: 25 },
    { width: 20 }
  ];

  const filename = `Выбытие_скота_по_шаблону_${formatDate(new Date())}.xlsx`;
  res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
  res.setHeader('Content-Disposition', `attachment; filename="${encodeURIComponent(filename)}"`);
  await workbook.xlsx.write(res);
  return res.end();
});

// JSON API endpoints
app.get('/get_farms', loginRequired, (req: Request, res: Response) => {
  const farmList = users
    .filter(u => u.user_type === 'farm' && u.farm_name && u.farm_name.trim() !== '')
    .map(u => u.farm_name!)
    .sort();
  res.json([...new Set(farmList)]);
});

app.get('/get_reasons/:category', loginRequired, (req: Request, res: Response) => {
  const category = String(req.params.category);
  const reasons = DISPOSAL_CATEGORIES[category] || [];
  res.json(reasons);
});

app.get('/get_stats_data', loginRequired, (req: Request, res: Response) => {
  const userType = req.session.user_type;
  const farmName = req.session.farm_name;
  const statsData = getStatisticsData(userType, farmName);
  res.json(statsData);
});

// Fix Categories
app.get('/fix_categories', loginRequired, adminRequired, (req: Request, res: Response) => {
  res.render('fix_categories');
});

app.post('/api/fix_categories', loginRequired, adminRequired, (req: Request, res: Response) => {
  for (const cow of cows) {
    const lower = cow.category.toLowerCase().trim();
    if (lower.includes('пад')) cow.category = 'падёж';
    else if (lower.includes('выбрак')) cow.category = 'выбраковка';
    else if (lower.includes('сан')) cow.category = 'санитарный';
  }
  res.json({ success: true, message: 'Категории успешно исправлены и нормализованы' });
});

// 404 Fallback
app.use((req: Request, res: Response) => {
  res.status(404).render('login');
});

// Error handling middleware
app.use((err: any, req: Request, res: Response, next: NextFunction) => {
  console.error('Server error:', err);
  res.status(500).send('Внутренняя ошибка сервера: ' + (err.message || 'Error'));
});

// Start Server on 0.0.0.0:3000
app.listen(Number(PORT), '0.0.0.0', () => {
  console.log(`Server started and listening on http://0.0.0.0:${PORT}`);
});
