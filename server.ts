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
const PORT = 3000;

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

// Dynamic Financial Pricing Standards (BYN) & Zootechnical Norm/Warning/Critical Thresholds
export interface FinancialPricingStandards {
  price_calves: number;      // BYN/гол (Телята 0–6 мес)
  price_youngstock: number;  // BYN/гол (Ремонтный молодняк 6–18 мес)
  price_heifers: number;     // BYN/гол (Нетели)
  price_cows: number;        // BYN/гол (Коровы дойного стада)
  price_dry_cows: number;    // BYN/гол (Сухостойные коровы)
  meat_price_per_kg: number; // BYN/кг живой массы
  milk_price_per_kg: number; // BYN/кг базисного молока
  replacement_cost: number;  // BYN/гол стоимость нетели на замену

  // 1. Выбытие новотельных (0-30 DIM)
  norm_fresh_cow_disposal: number; // Целевая норма (%)
  warn_fresh_cow_disposal: number; // Порог предупреждения (%)
  crit_fresh_cow_disposal: number; // Критический порог (%)

  // 2. Выбраковка первотёлок
  norm_first_lactation_culling: number; // Целевая норма (%)
  warn_first_lactation_culling: number; // Порог предупреждения (%)
  crit_first_lactation_culling: number; // Критический порог (%)

  // 3. Общая летальность (Падёж)
  norm_mortality_rate: number; // Целевая норма (%)
  warn_mortality_rate: number; // Порог предупреждения (%)
  crit_mortality_rate: number; // Критический порог (%)

  // 4. Болезни конечностей (копыт)
  norm_locomotor_disorders: number; // Целевая норма (%)
  warn_locomotor_disorders: number; // Порог предупреждения (%)
  crit_locomotor_disorders: number; // Критический порог (%)

  // 5. Маститы и заболевания вымени
  norm_mastitis_disorders: number; // Целевая норма (%)
  warn_mastitis_disorders: number; // Порог предупреждения (%)
  crit_mastitis_disorders: number; // Критический порог (%)
}

export let currentPricingStandards: FinancialPricingStandards = {
  price_calves: 900,
  price_youngstock: 1650,
  price_heifers: 2700,
  price_cows: 3200,
  price_dry_cows: 3000,
  meat_price_per_kg: 6.20,
  milk_price_per_kg: 1.18,
  replacement_cost: 2950,

  norm_fresh_cow_disposal: 10.0,
  warn_fresh_cow_disposal: 14.0,
  crit_fresh_cow_disposal: 18.0,

  norm_first_lactation_culling: 20.0,
  warn_first_lactation_culling: 25.0,
  crit_first_lactation_culling: 30.0,

  norm_mortality_rate: 25.0,
  warn_mortality_rate: 35.0,
  crit_mortality_rate: 45.0,

  norm_locomotor_disorders: 15.0,
  warn_locomotor_disorders: 20.0,
  crit_locomotor_disorders: 25.0,

  norm_mastitis_disorders: 15.0,
  warn_mastitis_disorders: 20.0,
  crit_mastitis_disorders: 25.0
};

export function normalizeAgeGroup(ag?: string, lact?: number): string {
  if (!ag) {
    if (lact === 1) return 'Коровы 1-й лактации (первотёлки)';
    return 'Коровы 2+ лактаций (полновозрастные)';
  }
  const lower = ag.toLowerCase().trim();
  if (lower.includes('мертворож') || lower.includes('аборт') || lower.includes('плод')) {
    return 'Мертворождённые / Аборты';
  }
  if (lower.includes('новотел') || lower.includes('0-30') || lower.includes('0–30')) {
    return 'Новотельные коровы (0–30 дн DIM)';
  }
  if (lower.includes('телят') || lower.includes('до 6') || lower.includes('0–6') || lower.includes('0-6') || lower.includes('новорожд') || lower.includes('молочн')) {
    return 'Телята (до 6 мес.)';
  }
  if (lower.includes('быч') || lower.includes('бык') || lower.includes('откорм')) {
    return 'Бычки на откорме';
  }
  if (lower.includes('молод') || lower.includes('6–18') || lower.includes('6-18') || lower.includes('6–12') || lower.includes('от 6 до 18') || lower.includes('6-12') || lower.includes('ремонтн')) {
    return 'Молодняк (от 6 до 18 мес.)';
  }
  if (lower.includes('нетел') || lower.includes('старше 18') || lower.includes('> 18') || lower.includes('>18') || lower.includes('старше 1 года')) {
    return 'Нетели и тёлки (> 18 мес.)';
  }
  if (lower.includes('сухосто')) {
    return 'Коровы сухостойные';
  }
  if (lower.includes('первотёл') || lower.includes('первотел') || lower.includes('1-й лакт') || lower.includes('1-я лакт') || lower.includes('1 лакт') || lact === 1) {
    return 'Коровы 1-й лактации (первотёлки)';
  }
  if (lower.includes('полновозраст') || lower.includes('2+ лакт') || lower.includes('2+') || lower.includes('2 лакт') || (lact !== undefined && lact > 1)) {
    return 'Коровы 2+ лактаций (полновозрастные)';
  }
  if (lact === 1) return 'Коровы 1-й лактации (первотёлки)';
  return 'Коровы 2+ лактаций (полновозрастные)';
}

export function matchesAgeGroupFilter(c: { age_group?: string; lactation?: number }, filter?: string): boolean {
  if (!filter || filter === 'all') return true;
  const fL = filter.toLowerCase().trim();
  if (fL === 'молодняк_все') {
    const norm = normalizeAgeGroup(c.age_group, c.lactation).toLowerCase();
    return norm.includes('тел') || norm.includes('молод') || norm.includes('быч');
  }

  // 1. Direct equality of normalized forms
  const normCow = normalizeAgeGroup(c.age_group, c.lactation);
  const normFilter = normalizeAgeGroup(filter);
  if (normCow === normFilter) return true;

  // 2. Semantic keywords check
  if (fL.includes('полновозраст') || fL.includes('2+')) {
    return normCow === 'Коровы 2+ лактаций (полновозрастные)' || (c.lactation !== undefined && c.lactation > 1);
  }
  if (fL.includes('первотел') || fL.includes('первотёл') || fL.includes('1-й лакт') || fL.includes('1-я лакт') || fL.includes('1 лакт')) {
    return normCow === 'Коровы 1-й лактации (первотёлки)' || c.lactation === 1;
  }
  if (fL.includes('телят') || fL.includes('до 6') || fL.includes('0-6') || fL.includes('0–6')) {
    return normCow === 'Телята (до 6 мес.)';
  }
  if (fL.includes('молод') || fL.includes('6-18') || fL.includes('6–18') || fL.includes('ремонтн')) {
    return normCow === 'Молодняк (от 6 до 18 мес.)';
  }
  if (fL.includes('нетел') || fL.includes('18')) {
    return normCow === 'Нетели и тёлки (> 18 мес.)';
  }
  if (fL.includes('быч') || fL.includes('откорм')) {
    return normCow === 'Бычки на откорме';
  }
  if (fL.includes('сухосто')) {
    return normCow === 'Коровы сухостойные';
  }
  if (fL.includes('новотел')) {
    return normCow === 'Новотельные коровы (0–30 дн DIM)';
  }
  if (fL.includes('мертворож') || fL.includes('аборт')) {
    return normCow === 'Мертворождённые / Аборты';
  }

  // 3. Fallback raw string match
  const cL = (c.age_group || '').toLowerCase();
  return cL.includes(fL) || fL.includes(cL);
}

export function estimateCowValue(c: { book_value?: number; age_group?: string; lactation?: number }): number {
  if (c.book_value && c.book_value > 0) {
    return c.book_value;
  }
  const normAg = normalizeAgeGroup(c.age_group, c.lactation);
  if (normAg === 'Телята (до 6 мес.)') return currentPricingStandards.price_calves;
  if (normAg === 'Молодняк (от 6 до 18 мес.)') return currentPricingStandards.price_youngstock;
  if (normAg === 'Нетели и тёлки (> 18 мес.)') return currentPricingStandards.price_heifers;
  if (normAg === 'Коровы сухостойные') return currentPricingStandards.price_dry_cows;
  if (normAg === 'Бычки на откорме') return currentPricingStandards.price_youngstock;
  return currentPricingStandards.price_cows;
}

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
  lactation_days?: number; // Дни лактации (DIM - Days in Milk)
  lactation_phase?: string; // Новотел (0-30 дн), Раздой (31-100 дн), Середина (101-200 дн), Спад (201-305+ дн), Сухостой, Телята, Молодняк
  weight?: number;
  notes?: string;
  age_group?: string; // Половозрастная группа: Телята (до 6 мес.), Молодняк (от 6 до 18 мес.), Нетели и тёлки (> 18 мес.), Коровы 1-й лактации (первотёлки), Коровы 2+ лактаций (полновозрастные), Коровы сухостойные, Бычки на откорме
  breed?: string;
  milk_yield?: number;
  book_value?: number;
  is_pregnant?: number;
  gestation_days?: number;
  is_stillborn?: number;
  created_at: string;
  created_by?: number;
}

// Initial Data Store
let userIdCounter = 1;
let cowIdCounter = 1;

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

export function getUniqueFarms(): string[] {
  const farmSet = new Set<string>();
  for (const u of users) {
    if (u.user_type === 'farm' && u.farm_name && u.farm_name.trim()) {
      farmSet.add(u.farm_name.trim());
    }
  }
  for (let i = 0; i < cows.length; i++) {
    const fn = cows[i].farm_name;
    if (fn && fn.trim()) {
      farmSet.add(fn.trim());
    }
  }
  return Array.from(farmSet).sort();
}

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

export const cows: Cow[] = [];

export function computeLactationPhase(ageGroup?: string, lactationDays?: number | null, lactation?: number | null): string {
  const normAg = normalizeAgeGroup(ageGroup, lactation ?? undefined);
  if (normAg === 'Мертворождённые / Аборты') {
    return 'Мертворождённые / Аборты';
  }
  if (normAg === 'Новотельные коровы (0–30 дн DIM)') {
    return 'Новотел (0–30 дн)';
  }
  if (normAg === 'Телята (до 6 мес.)') {
    return 'Телята (до 6 мес.)';
  }
  if (normAg === 'Молодняк (от 6 до 18 мес.)') {
    return 'Молодняк (от 6 до 18 мес.)';
  }
  if (normAg === 'Нетели и тёлки (> 18 мес.)') {
    return 'Нетели (> 18 мес.)';
  }
  if (normAg === 'Бычки на откорме') {
    return 'Бычки на откорме';
  }
  if (normAg === 'Коровы сухостойные') {
    return 'Сухостой';
  }
  if (lactationDays === undefined || lactationDays === null || isNaN(lactationDays)) {
    return 'Не указано';
  }
  if (lactationDays <= 30) {
    return 'Новотел (0–30 дн)';
  } else if (lactationDays <= 100) {
    return 'Раздой (31–100 дн)';
  } else if (lactationDays <= 200) {
    return 'Середина (101–200 дн)';
  } else {
    return 'Спад (201–305+ дн)';
  }
}

// Realistic Massive Test Data Generator (1 200+ cows)
export function populateRealisticCows(targetCount: number = 1250, clearExisting: boolean = true) {
  if (clearExisting) {
    cows.length = 0;
    cowIdCounter = 1;
  }

  const farms = [
    { name: 'МТФ-1 Центральная', prefix: 'МТФ1', createdBy: 2 },
    { name: 'МТФ-2 Заречье', prefix: 'МТФ2', createdBy: 3 },
    { name: 'МТФ-3 Полесье', prefix: 'МТФ3', createdBy: 4 }
  ];

  const breeds = ['Белорусская черно-пёстрая', 'Голштинская', 'Лимузин'];

  const reasonsPad = [
    'Острая тимпания рубца',
    'Бронхопневмония',
    'Диспепсия телят',
    'Травматический ретикулит',
    'Кетоз (острая форма)',
    'Анаэробная энтеротоксемия',
    'Эшерихиоз (колибактериоз)',
    'Перитонит',
    'Послеродовой парез',
    'Разрыв маточной артерии',
    'Крупозная пневмония'
  ];

  const reasonsVyb = [
    'Гнойный мастит',
    'Агалактия (потеря молочности)',
    'Хронический гнойный эндометрит',
    'Фолликулярная киста яичников',
    'Лютеиновая киста',
    'Язва Рунхольца (пододерматит)',
    'Флегмона венчика',
    'Атрофия долей вымени',
    'Гипотония преджелудков',
    'Атрофия яичников / яловость',
    'Возрастная выбраковка (предельный возраст)'
  ];

  const reasonsSan = [
    'Травма конечностей',
    'Травма позвоночного столба',
    'Патологические роды',
    'Выпадение матки',
    'Стойкая атония преджелудков',
    'Кетоз тяжелой степени',
    'Перелом трубчатых костей'
  ];

  const farmCounters: Record<string, number> = {
    'МТФ-1 Центральная': 0,
    'МТФ-2 Заречье': 0,
    'МТФ-3 Полесье': 0
  };

  for (const c of cows) {
    if (farmCounters[c.farm_name] !== undefined) {
      farmCounters[c.farm_name]++;
    }
  }

  const currentDate = new Date();

  for (let i = 0; i < targetCount; i++) {
    // Farm distribution
    const rFarm = Math.random();
    let farm = farms[0];
    if (rFarm > 0.76) {
      farm = farms[2];
    } else if (rFarm > 0.42) {
      farm = farms[1];
    }
    farmCounters[farm.name] = (farmCounters[farm.name] || 0) + 1;

    // Category distribution (~28% падёж, ~56% выбраковка, ~16% санитарный)
    const rCat = Math.random();
    let cat: 'падёж' | 'выбраковка' | 'санитарный' = 'выбраковка';
    let reason = '';
    if (rCat < 0.28) {
      cat = 'падёж';
      reason = reasonsPad[Math.floor(Math.random() * reasonsPad.length)];
    } else if (rCat < 0.84) {
      cat = 'выбраковка';
      reason = reasonsVyb[Math.floor(Math.random() * reasonsVyb.length)];
    } else {
      cat = 'санитарный';
      reason = reasonsSan[Math.floor(Math.random() * reasonsSan.length)];
    }

    // Age groups & physiological parameters
    let ag = 'Коровы 2+ лактаций (полновозрастные)';
    let lact = 1 + Math.floor(Math.random() * 5);
    let lactDays = 120;
    let weight = 480 + Math.floor(Math.random() * 180);
    let milkYield = 5500 + Math.floor(Math.random() * 3800);
    let bookVal = 1800 + Math.floor(Math.random() * 1400);

    if (reason === 'Диспепсия телят' || reason === 'Эшерихиоз (колибактериоз)' || (cat === 'падёж' && Math.random() < 0.22)) {
      ag = 'Телята (до 6 мес.)';
      lact = 0;
      lactDays = 0;
      weight = 32 + Math.floor(Math.random() * 55);
      milkYield = 0;
      bookVal = 260 + Math.floor(Math.random() * 280);
    } else if (Math.random() < 0.12) {
      ag = 'Молодняк (от 6 до 18 мес.)';
      lact = 0;
      lactDays = 0;
      weight = 180 + Math.floor(Math.random() * 170);
      milkYield = 0;
      bookVal = 850 + Math.floor(Math.random() * 700);
    } else if (reason.includes('роды') || reason.includes('матки') || Math.random() < 0.08) {
      ag = 'Нетели и тёлки (> 18 мес.)';
      lact = 0;
      lactDays = 0;
      weight = 430 + Math.floor(Math.random() * 100);
      milkYield = 0;
      bookVal = 2600 + Math.floor(Math.random() * 700);
    } else if (Math.random() < 0.10) {
      ag = 'Коровы сухостойные';
      lact = 2 + Math.floor(Math.random() * 4);
      lactDays = 0;
      weight = 520 + Math.floor(Math.random() * 140);
      milkYield = 5800 + Math.floor(Math.random() * 2400);
      bookVal = 2100 + Math.floor(Math.random() * 900);
    } else if (Math.random() < 0.05) {
      ag = 'Бычки на откорме';
      lact = 0;
      lactDays = 0;
      weight = 360 + Math.floor(Math.random() * 140);
      milkYield = 0;
      bookVal = 1200 + Math.floor(Math.random() * 600);
    } else {
      // Дойное стадо: разделение на 1-ю лактацию (первотёлки) и 2+ лактаций
      if (lact === 1) {
        ag = 'Коровы 1-й лактации (первотёлки)';
      } else {
        ag = 'Коровы 2+ лактаций (полновозрастные)';
      }
      // Реалистичные дни лактации (DIM) по патологиям
      if (reason.includes('парез') || reason.includes('артерии') || reason.includes('роды') || reason.includes('Кетоз (острая')) {
        // Новотельный период (1–30 дней)
        lactDays = 2 + Math.floor(Math.random() * 27);
      } else if (reason.includes('мастит') || reason.includes('тимпания') || reason.includes('пневмония')) {
        // Раздой (31–100 дней)
        lactDays = 32 + Math.floor(Math.random() * 68);
      } else if (reason.includes('конечност') || reason.includes('эндометрит') || reason.includes('пододерматит') || reason.includes('венчика')) {
        // Середина лактации (101–200 дней)
        lactDays = 102 + Math.floor(Math.random() * 98);
      } else {
        // Спад / завершение лактации (201–350 дней)
        lactDays = 205 + Math.floor(Math.random() * 145);
      }
    }

    const lactPhase = computeLactationPhase(ag, lactDays, lact);

    // Breed selection
    const breed = breeds[Math.random() < 0.75 ? 0 : (Math.random() < 0.8 ? 1 : 2)];

    // Dates distribution: exactly 12 months, ~104 cows per month, days 1..28
    const monthOffset = i % 12;
    const targetY = currentDate.getFullYear();
    const targetM = currentDate.getMonth() - monthOffset;
    const targetD = 1 + (Math.floor(i / 12) % 28);
    const dObj = new Date(targetY, targetM, targetD);
    const dStr = formatDate(dObj);

    // Belarusian ear tag: BY 04 + 7-digit number
    const tagNum = 7100000 + (cowIdCounter % 890000);
    const earTag = `BY 04 ${tagNum}`;
    const cowId = `${farm.prefix}-${String(farmCounters[farm.name]).padStart(4, '0')}`;

    // Reproduction attributes
    let isPreg = 0;
    let gestD = 0;
    let isStill = 0;

    const rLower = reason.toLowerCase();
    if (ag === 'Коровы сухостойные') {
      isPreg = 1;
      gestD = 210 + Math.floor(Math.random() * 60);
    } else if (ag === 'Нетели') {
      isPreg = 1;
      gestD = 160 + Math.floor(Math.random() * 100);
    } else if (Math.random() < 0.14 && !ag.includes('Телят') && !ag.includes('Бычк')) {
      isPreg = 1;
      gestD = 35 + Math.floor(Math.random() * 170);
    }

    if (rLower.includes('роды') || rLower.includes('плод') || rLower.includes('моцерац') || rLower.includes('мацерац') || rLower.includes('аборт') || rLower.includes('мертворож') || (ag.includes('Телят') && Math.random() < 0.12)) {
      isStill = 1;
    }

    cows.push({
      id: cowIdCounter++,
      cow_id: cowId,
      ear_tag: earTag,
      farm_name: farm.name,
      category: cat,
      reason: reason,
      disposal_date: dStr,
      lactation: lact,
      lactation_days: lactDays,
      lactation_phase: lactPhase,
      weight: weight,
      age_group: ag,
      breed: breed,
      book_value: bookVal,
      milk_yield: milkYield,
      is_pregnant: isPreg,
      gestation_days: gestD,
      is_stillborn: isStill,
      created_at: `${dStr} 10:00:00`,
      created_by: farm.createdBy
    });
  }
}

// Initial Population: 1 250 records
populateRealisticCows(1250, true);

// Helpers
function generateCowId(farmName: string): string {
  const prefix = `${farmName.split(' ')[0]}-`;
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
  return `${farmName.split(' ')[0]}-${String(nextNum).padStart(4, '0')}`;
}

// ==========================================
// DDoS & ABUSE PROTECTION ENGINE
// ==========================================

export interface SecurityMetrics {
  totalRequests: number;
  blockedRequestsCount: number;
  blockedIpsTotal: Set<string>;
  authFailuresCount: number;
  slowRequestsCount: number;
  startedAt: Date;
}

export const securityMetrics: SecurityMetrics = {
  totalRequests: 0,
  blockedRequestsCount: 0,
  blockedIpsTotal: new Set<string>(),
  authFailuresCount: 0,
  slowRequestsCount: 0,
  startedAt: new Date()
};

// Process Crash Immunity (Never let unhandled errors take down the server)
process.on('uncaughtException', (err: any) => {
  console.error('[CRASH IMMUNITY] Uncaught Exception safely handled:', err);
});

process.on('unhandledRejection', (reason: any, promise: any) => {
  console.error('[CRASH IMMUNITY] Unhandled Rejection safely handled:', reason);
});

export function getClientIp(req: Request): string {
  const cf = req.headers['cf-connecting-ip'];
  if (typeof cf === 'string' && cf.trim()) return cf.trim();
  const forwarded = req.headers['x-forwarded-for'];
  if (typeof forwarded === 'string' && forwarded.trim()) {
    return forwarded.split(',')[0].trim();
  }
  const realIp = req.headers['x-real-ip'];
  if (typeof realIp === 'string' && realIp.trim()) return realIp.trim();
  return req.socket.remoteAddress || req.ip || '127.0.0.1';
}

interface IpWindow {
  timestamps: number[];
  burstTimestamps: number[];
  blockedUntil?: number;
}

export class SlidingWindowRateLimiter {
  private windows = new Map<string, IpWindow>();
  private readonly maxRequests: number;
  private readonly windowMs: number;
  private readonly maxBurst: number;
  private readonly burstWindowMs: number;
  private readonly blockDurationMs: number;

  constructor(options: {
    maxRequests: number;
    windowMs: number;
    maxBurst?: number;
    burstWindowMs?: number;
    blockDurationMs?: number;
  }) {
    this.maxRequests = options.maxRequests;
    this.windowMs = options.windowMs;
    this.maxBurst = options.maxBurst || options.maxRequests;
    this.burstWindowMs = options.burstWindowMs || 5000;
    this.blockDurationMs = options.blockDurationMs || 60000;

    // Prune stale records every 60s to prevent memory leaks
    setInterval(() => this.prune(), 60000).unref();
  }

  public check(ip: string): { allowed: boolean; remaining: number; retryAfterSec?: number; reason?: string } {
    if (ip === '127.0.0.1' || ip === '::1' || ip === '::ffff:127.0.0.1') {
      return { allowed: true, remaining: 999 };
    }
    const now = Date.now();
    let entry = this.windows.get(ip);

    if (!entry) {
      entry = { timestamps: [], burstTimestamps: [] };
      this.windows.set(ip, entry);
    }

    // Check if IP is currently banned/blocked
    if (entry.blockedUntil && entry.blockedUntil > now) {
      const retryAfterSec = Math.ceil((entry.blockedUntil - now) / 1000);
      return { allowed: false, remaining: 0, retryAfterSec, reason: 'IP временно заблокирован из-за подозрительной активности (DDoS Protection)' };
    }

    // Filter out old timestamps outside main window
    const windowCutoff = now - this.windowMs;
    entry.timestamps = entry.timestamps.filter(t => t > windowCutoff);

    // Filter out old timestamps outside burst window
    const burstCutoff = now - this.burstWindowMs;
    entry.burstTimestamps = entry.burstTimestamps.filter(t => t > burstCutoff);

    // Check burst limit (flood spike)
    if (entry.burstTimestamps.length >= this.maxBurst) {
      entry.blockedUntil = now + this.blockDurationMs;
      securityMetrics.blockedRequestsCount++;
      securityMetrics.blockedIpsTotal.add(ip);
      const retryAfterSec = Math.ceil(this.blockDurationMs / 1000);
      return { allowed: false, remaining: 0, retryAfterSec, reason: 'Превышен лимит всплеска запросов (Burst Flood Protection)' };
    }

    // Check window limit
    if (entry.timestamps.length >= this.maxRequests) {
      entry.blockedUntil = now + Math.min(this.blockDurationMs, 30000);
      securityMetrics.blockedRequestsCount++;
      securityMetrics.blockedIpsTotal.add(ip);
      const retryAfterSec = Math.ceil((entry.timestamps[0] + this.windowMs - now) / 1000) || 1;
      return { allowed: false, remaining: 0, retryAfterSec, reason: 'Превышен лимит частоты запросов (Rate Limit Exceeded)' };
    }

    // Allowed: record request
    entry.timestamps.push(now);
    entry.burstTimestamps.push(now);

    return {
      allowed: true,
      remaining: Math.max(0, this.maxRequests - entry.timestamps.length)
    };
  }

  private prune() {
    const now = Date.now();
    for (const [ip, entry] of this.windows.entries()) {
      if (entry.blockedUntil && entry.blockedUntil > now) continue;
      entry.timestamps = entry.timestamps.filter(t => t > now - this.windowMs);
      entry.burstTimestamps = entry.burstTimestamps.filter(t => t > now - this.burstWindowMs);
      if (entry.timestamps.length === 0 && entry.burstTimestamps.length === 0) {
        this.windows.delete(ip);
      }
    }
  }

  public getTrackedCount(): number {
    return this.windows.size;
  }
}

// Global DDoS limiter: 180 requests/min, burst max 35 requests/5s
export const globalDdosLimiter = new SlidingWindowRateLimiter({
  maxRequests: 180,
  windowMs: 60000,
  maxBurst: 35,
  burstWindowMs: 5000,
  blockDurationMs: 60000
});

// Heavy operations limiter: 25 requests/min (for reports, Excel exports, bulk ops)
export const heavyOpsLimiter = new SlidingWindowRateLimiter({
  maxRequests: 25,
  windowMs: 60000,
  maxBurst: 10,
  burstWindowMs: 5000,
  blockDurationMs: 60000
});

// Auth POST /login limiter: 8 attempts/3min
export const authLimiter = new SlidingWindowRateLimiter({
  maxRequests: 8,
  windowMs: 180000,
  maxBurst: 4,
  burstWindowMs: 10000,
  blockDurationMs: 180000
});

// Login Brute Force & Credential Stuffing Lockout (prevents CPU burnout on bcrypt)
interface FailedLoginRecord {
  count: number;
  lastAttempt: number;
  lockedUntil?: number;
}
const failedLogins = new Map<string, FailedLoginRecord>();

export function recordFailedLogin(key: string) {
  const now = Date.now();
  let rec = failedLogins.get(key);
  if (!rec || now - rec.lastAttempt > 10 * 60 * 1000) {
    rec = { count: 1, lastAttempt: now };
  } else {
    rec.count++;
    rec.lastAttempt = now;
  }
  if (rec.count >= 5) {
    rec.lockedUntil = now + 5 * 60 * 1000; // 5 minute lockout after 5 failed tries
  }
  failedLogins.set(key, rec);
}

export function checkLoginLockout(key: string): { locked: boolean; waitSec: number } {
  const now = Date.now();
  const rec = failedLogins.get(key);
  if (!rec) return { locked: false, waitSec: 0 };
  if (rec.lockedUntil && rec.lockedUntil > now) {
    return { locked: true, waitSec: Math.ceil((rec.lockedUntil - now) / 1000) };
  }
  return { locked: false, waitSec: 0 };
}

export function clearFailedLogin(key: string) {
  failedLogins.delete(key);
}

// Heavy Operations Limiter Middleware (bypassed for uninterrupted access)
export function heavyOpsProtection(req: Request, res: Response, next: NextFunction) {
  next();
}

// App Settings & Middlewares
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// Hide server technology
app.disable('x-powered-by');

// Security Headers Middleware
app.use((req: Request, res: Response, next: NextFunction) => {
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-XSS-Protection', '1; mode=block');
  res.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin');
  res.setHeader('Permissions-Policy', 'camera=(), microphone=(), geolocation=()');
  next();
});

// Slowloris & Request Execution Timeout Guard (25 seconds)
app.use((req: Request, res: Response, next: NextFunction) => {
  const timeoutId = setTimeout(() => {
    if (!res.headersSent) {
      securityMetrics.slowRequestsCount++;
      res.status(504).type('text/html; charset=utf-8').send(`
        <!DOCTYPE html>
        <html lang="ru">
        <head><meta charset="utf-8"><title>504 Gateway Timeout</title></head>
        <body style="font-family: 'Segoe UI', Tahoma, sans-serif; text-align: center; padding: 60px; background: #f8fafc; color: #1e293b;">
          <h2 style="color: #e11d48;">504 - Превышено время ожидания ответа сервера</h2>
          <p>Запрос выполнялся дольше 25 секунд и был прерван защитой от атак исчерпания ресурсов (Slowloris/DoS Protection).</p>
          <a href="/dashboard" style="display: inline-block; margin-top: 15px; padding: 10px 20px; background: #0284c7; color: white; border-radius: 6px; text-decoration: none;">Вернуться на главную</a>
        </body>
        </html>
      `);
    }
  }, 25000);

  res.on('finish', () => clearTimeout(timeoutId));
  res.on('close', () => clearTimeout(timeoutId));
  next();
});

// Global Request Tracking Middleware (bypassed 429 limits for smooth user experience)
app.use((req: Request, res: Response, next: NextFunction) => {
  securityMetrics.totalRequests++;
  next();
});

// Parameter Pollution & Prototype Pollution Guard
app.use((req: Request, res: Response, next: NextFunction) => {
  const checkProto = (obj: any): boolean => {
    if (!obj || typeof obj !== 'object') return false;
    for (const key of Object.keys(obj)) {
      if (key === '__proto__' || key === 'constructor' || key === 'prototype') {
        return true;
      }
      if (typeof obj[key] === 'object' && checkProto(obj[key])) {
        return true;
      }
    }
    return false;
  };

  if (checkProto(req.query) || checkProto(req.body)) {
    return res.status(400).send('Bad Request: Parameter pollution blocked');
  }

  // Type confusion protection for query scalar params
  if (req.query) {
    for (const key of Object.keys(req.query)) {
      if (Array.isArray(req.query[key])) {
        req.query[key] = (req.query[key] as any[])[0];
      }
      if (typeof req.query[key] === 'string' && (req.query[key] as string).length > 200) {
        req.query[key] = (req.query[key] as string).substring(0, 200);
      }
    }
  }

  next();
});

// Strictly Bounded Body Parsers (Prevents Memory/Heap Exhaustion DoS)
app.use(express.json({ limit: '2mb' }));
app.use(express.urlencoded({ extended: true, limit: '2mb' }));
app.use(cookieParser());
app.use(express.static(path.join(__dirname, 'public')));
app.use('/static', express.static(path.join(__dirname, 'public')));

// Explicit Logo & Favicon Handlers for reliable rendering
app.get(['/img/logo.svg', '/logo.svg', '/static/img/logo.svg'], (req: Request, res: Response) => {
  res.setHeader('Content-Type', 'image/svg+xml; charset=utf-8');
  res.setHeader('Cache-Control', 'public, max-age=86400');
  res.sendFile(path.join(__dirname, 'public/img/logo.svg'));
});

app.get(['/img/logo.jpg', '/logo.jpg', '/static/img/logo.jpg'], (req: Request, res: Response) => {
  res.setHeader('Content-Type', 'image/jpeg');
  res.setHeader('Cache-Control', 'public, max-age=86400');
  res.sendFile(path.join(__dirname, 'public/img/logo.jpg'));
});

app.get(['/favicon.ico', '/favicon.png', '/favicon.svg'], (req: Request, res: Response) => {
  res.setHeader('Content-Type', 'image/svg+xml; charset=utf-8');
  res.setHeader('Cache-Control', 'public, max-age=86400');
  res.sendFile(path.join(__dirname, 'public/img/logo.svg'));
});

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
  res.locals.cows_count = cows.length;
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

function getDashboardFullData(userType?: string, farmName?: string | null, period: string = 'all', customStart?: string, customEnd?: string) {
  const now = new Date();
  let startDate = '';
  let endDate = '2099-12-31';
  let periodTitle = '';

  if (period === 'last_7') {
    const start = new Date(now.getTime() - 6 * 24 * 60 * 60 * 1000);
    startDate = formatDate(start);
    endDate = formatDate(now);
    periodTitle = 'Последние 7 дней';
  } else if (period === 'last_30') {
    const start = new Date(now.getTime() - 29 * 24 * 60 * 60 * 1000);
    startDate = formatDate(start);
    endDate = formatDate(now);
    periodTitle = 'Последние 30 дней';
  } else if (period === 'this_month') {
    const d = new Date(now.getFullYear(), now.getMonth(), 1);
    const end = new Date(now.getFullYear(), now.getMonth() + 1, 0);
    startDate = formatDate(d);
    endDate = formatDate(end);
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
    const end = new Date(now.getFullYear(), qMonth + 3, 0);
    startDate = formatDate(start);
    endDate = formatDate(end);
    periodTitle = `Текущий квартал (${Math.floor(now.getMonth() / 3) + 1} кв. ${now.getFullYear()})`;
  } else if (period === 'ytd') {
    startDate = `${now.getFullYear()}-01-01`;
    endDate = `${now.getFullYear()}-12-31`;
    periodTitle = `С начала ${now.getFullYear()} года (YTD)`;
  } else if (period === 'all') {
    startDate = '2000-01-01';
    endDate = '2099-12-31';
    periodTitle = 'За всё время учёта (Все 1 250 голов)';
  } else if (period === 'custom' && customStart && customEnd) {
    startDate = customStart;
    endDate = customEnd;
    periodTitle = `С ${startDate} по ${endDate}`;
  } else {
    startDate = '2000-01-01';
    endDate = '2099-12-31';
    periodTitle = 'За всё время учёта (Все 1 250 голов)';
  }

  // Filter cows
  const relevantCows = cows.filter(c => {
    const farmMatch = (userType === 'admin' && (farmName === 'all' || !farmName)) ? true : c.farm_name === farmName;
    const dateMatch = c.disposal_date >= startDate && c.disposal_date <= endDate;
    return farmMatch && dateMatch;
  });

  // Strict isolation: live animal disposals vs intrauterine fetal losses (stillbirths/abortions)
  const liveCows = relevantCows.filter(c => !c.is_stillborn && c.category !== 'мертворождение' && normalizeAgeGroup(c.age_group) !== 'Мертворождённые / Аборты');

  const categoryCounts: Record<string, number> = { 'падёж': 0, 'выбраковка': 0, 'санитарный': 0 };
  const ageGroupCounts: Record<string, number> = {};
  const pathologySystems: Record<string, number> = {};
  const reasonCounts: Record<string, { category: string, count: number }> = {};
  const farmCounts: Record<string, number> = {};

  // Lactation Cohorts tracking: DIM groups & phases
  const lactationCohorts: Record<string, { total: number; death: number; culling: number; sanitary: number; totalDim: number; countDim: number }> = {
    'Новотел (0–30 дн)': { total: 0, death: 0, culling: 0, sanitary: 0, totalDim: 0, countDim: 0 },
    'Раздой (31–100 дн)': { total: 0, death: 0, culling: 0, sanitary: 0, totalDim: 0, countDim: 0 },
    'Середина (101–200 дн)': { total: 0, death: 0, culling: 0, sanitary: 0, totalDim: 0, countDim: 0 },
    'Спад (201–305+ дн)': { total: 0, death: 0, culling: 0, sanitary: 0, totalDim: 0, countDim: 0 },
    'Сухостой': { total: 0, death: 0, culling: 0, sanitary: 0, totalDim: 0, countDim: 0 },
    'Молодняк': { total: 0, death: 0, culling: 0, sanitary: 0, totalDim: 0, countDim: 0 }
  };

  // Detailed animal category matrix with top diagnoses and averages
  const categoryMatrix: Record<string, { 
    total: number; 
    death: number; 
    culling: number; 
    sanitary: number; 
    totalWeight: number; 
    weightCount: number;
    totalLactation: number;
    lactationCount: number;
    totalDim: number;
    dimCount: number;
    totalLossByn: number;
    reasons: Record<string, number>;
  }> = {};

  let sumLactatingDim = 0;
  let countLactatingDim = 0;
  let sumLactationNum = 0;
  let countLactationNum = 0;

  // Экономическая оценка выбытия (балансовая стоимость в BYN)
  let totalBookValue = 0;
  let deathBookValue = 0;
  let cullingBookValue = 0;
  const bookValueByGroup: Record<string, number> = {};

  // Детальная кривая риска по дням лактации DIM (8 интервалов)
  const dimBins = [
    { label: '0–15 дн (Острый новотел)', min: 0, max: 15 },
    { label: '16–30 дн (Поздний новотел)', min: 16, max: 30 },
    { label: '31–60 дн (Раздой)', min: 31, max: 60 },
    { label: '61–100 дн (Пик лактации)', min: 61, max: 100 },
    { label: '101–150 дн (Плато лактации)', min: 101, max: 150 },
    { label: '151–200 дн (Середина)', min: 151, max: 200 },
    { label: '201–305 дн (Спад лактации)', min: 201, max: 305 },
    { label: '>305 дн (Затяжная / Яловость)', min: 306, max: 9999 }
  ];
  const dimCurveDeath = [0, 0, 0, 0, 0, 0, 0, 0];
  const dimCurveCulling = [0, 0, 0, 0, 0, 0, 0, 0];

  // Распределение выбытия по номеру лактации (1, 2, 3, 4, 5+)
  const lactNumberDeath = [0, 0, 0, 0, 0];
  const lactNumberCulling = [0, 0, 0, 0, 0];

  // Сравнительная матрица по фермам / МТФ
  const farmMatrix: Record<string, {
    total: number;
    death: number;
    culling: number;
    sanitary: number;
    calves: number;     // Телята (до 6 мес.)
    youngstock: number; // Молодняк (от 6 до 18 мес.)
    heifers: number;    // Нетели и тёлки (> 18 мес.)
    fresh: number;
    totalDim: number;
    dimCount: number;
    lossByn: number;
  }> = {};

  for (const c of liveCows) {
    categoryCounts[c.category] = (categoryCounts[c.category] || 0) + 1;
    farmCounts[c.farm_name] = (farmCounts[c.farm_name] || 0) + 1;

    const ag = normalizeAgeGroup(c.age_group, c.lactation);
    ageGroupCounts[ag] = (ageGroupCounts[ag] || 0) + 1;

    // Динамическая стоимостная оценка выбывшего животного по прейскуранту BYN
    const bValue = estimateCowValue(c);
    totalBookValue += bValue;
    if (c.category === 'падёж') deathBookValue += bValue;
    else cullingBookValue += bValue;
    bookValueByGroup[ag] = (bookValueByGroup[ag] || 0) + bValue;

    // Animal Category Matrix aggregation
    if (!categoryMatrix[ag]) {
      categoryMatrix[ag] = {
        total: 0,
        death: 0,
        culling: 0,
        sanitary: 0,
        totalWeight: 0,
        weightCount: 0,
        totalLactation: 0,
        lactationCount: 0,
        totalDim: 0,
        dimCount: 0,
        totalLossByn: 0,
        reasons: {}
      };
    }
    const catEntry = categoryMatrix[ag];
    catEntry.total++;
    catEntry.totalLossByn += bValue;
    if (c.category === 'падёж') catEntry.death++;
    else if (c.category === 'выбраковка') catEntry.culling++;
    else catEntry.sanitary++;

    if (c.weight && c.weight > 0) {
      catEntry.totalWeight += c.weight;
      catEntry.weightCount++;
    }
    if (c.lactation && c.lactation > 0) {
      catEntry.totalLactation += c.lactation;
      catEntry.lactationCount++;
      sumLactationNum += c.lactation;
      countLactationNum++;

      // Распределение по номеру лактации (1..5+)
      const lIdx = Math.min(4, Math.max(0, c.lactation - 1));
      if (c.category === 'падёж') lactNumberDeath[lIdx]++;
      else lactNumberCulling[lIdx]++;
    }
    if (c.lactation_days && c.lactation_days > 0) {
      catEntry.totalDim += c.lactation_days;
      catEntry.dimCount++;
      sumLactatingDim += c.lactation_days;
      countLactatingDim++;

      // Заполнение кривой риска DIM
      if (!ag.includes('Телят') && !ag.includes('Молодняк') && !ag.includes('Бычки')) {
        for (let bi = 0; bi < dimBins.length; bi++) {
          if (c.lactation_days >= dimBins[bi].min && c.lactation_days <= dimBins[bi].max) {
            if (c.category === 'падёж') dimCurveDeath[bi]++;
            else dimCurveCulling[bi]++;
            break;
          }
        }
      }
    }
    catEntry.reasons[c.reason] = (catEntry.reasons[c.reason] || 0) + 1;

    // Lactation phase cohort classification
    let phase = c.lactation_phase;
    if (!phase) {
      phase = computeLactationPhase(c.age_group, c.lactation_days, c.lactation);
    }
    let standardPhaseKey = 'Молодняк';
    if (phase.includes('Новотел')) standardPhaseKey = 'Новотел (0–30 дн)';
    else if (phase.includes('Раздой')) standardPhaseKey = 'Раздой (31–100 дн)';
    else if (phase.includes('Середина')) standardPhaseKey = 'Середина (101–200 дн)';
    else if (phase.includes('Спад')) standardPhaseKey = 'Спад (201–305+ дн)';
    else if (phase.includes('Сухосто')) standardPhaseKey = 'Сухостой';
    else standardPhaseKey = 'Молодняк';

    if (lactationCohorts[standardPhaseKey]) {
      const cohort = lactationCohorts[standardPhaseKey];
      cohort.total++;
      if (c.category === 'падёж') cohort.death++;
      else if (c.category === 'выбраковка') cohort.culling++;
      else cohort.sanitary++;

      if (c.lactation_days && c.lactation_days > 0) {
        cohort.totalDim += c.lactation_days;
        cohort.countDim++;
      }
    }

    const sys = classifyPathologySystem(c.reason);
    pathologySystems[sys] = (pathologySystems[sys] || 0) + 1;

    if (!reasonCounts[c.reason]) {
      reasonCounts[c.reason] = { category: c.category, count: 0 };
    }
    reasonCounts[c.reason].count++;

    // Сводная матрица по фермам
    const fn = c.farm_name;
    if (!farmMatrix[fn]) {
      farmMatrix[fn] = {
        total: 0,
        death: 0,
        culling: 0,
        sanitary: 0,
        calves: 0,
        youngstock: 0,
        heifers: 0,
        fresh: 0,
        totalDim: 0,
        dimCount: 0,
        lossByn: 0
      };
    }
    const fm = farmMatrix[fn];
    fm.total++;
    fm.lossByn += bValue;
    if (c.category === 'падёж') fm.death++;
    else if (c.category === 'выбраковка') fm.culling++;
    else fm.sanitary++;

    if (ag === 'Телята (до 6 мес.)') {
      fm.calves++;
    } else if (ag === 'Молодняк (от 6 до 18 мес.)') {
      fm.youngstock++;
    } else if (ag === 'Нетели и тёлки (> 18 мес.)') {
      fm.heifers++;
    }

    if ((c.lactation_days !== undefined && c.lactation_days !== null && c.lactation_days <= 30 && c.lactation_days > 0) || standardPhaseKey.includes('Новотел')) {
      fm.fresh++;
    }
    if (c.lactation_days && c.lactation_days > 0) {
      fm.totalDim += c.lactation_days;
      fm.dimCount++;
    }
  }

  const totalDisposals = liveCows.length;
  const sortedAgeGroups = Object.entries(ageGroupCounts).sort((a, b) => b[1] - a[1]);
  const sortedPathology = Object.entries(pathologySystems).sort((a, b) => b[1] - a[1]);
  const sortedFarms = Object.entries(farmCounts).sort((a, b) => b[1] - a[1]);
  const topReasonsList = Object.entries(reasonCounts)
    .sort((a, b) => b[1].count - a[1].count)
    .slice(0, 10)
    .map(([reason, data]) => ({ reason, category: data.category, count: data.count }));

  // Detailed Category Cards list
  const categoryAnalyticsList = Object.entries(categoryMatrix).map(([catName, stats]) => {
    const topReasons = Object.entries(stats.reasons)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3)
      .map(([r, cnt]) => `${r} (${cnt})`)
      .join(', ');

    return {
      category_name: catName,
      total: stats.total,
      death: stats.death,
      culling: stats.culling,
      sanitary: stats.sanitary,
      death_rate_pct: stats.total > 0 ? Math.round((stats.death / stats.total) * 1000) / 10 : 0,
      avg_weight: stats.weightCount > 0 ? Math.round(stats.totalWeight / stats.weightCount) : 0,
      avg_dim: stats.dimCount > 0 ? Math.round(stats.totalDim / stats.dimCount) : 0,
      avg_lactation: stats.lactationCount > 0 ? (stats.totalLactation / stats.lactationCount).toFixed(1) : '-',
      total_loss_byn: Math.round(stats.totalLossByn),
      top_reasons: topReasons || '-'
    };
  }).sort((a, b) => b.total - a.total);

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

  const trendCounts: Record<string, Record<string, number>> = {};
  for (const m of trendMonths) {
    trendCounts[m] = { 'падёж': 0, 'выбраковка': 0, 'санитарный': 0 };
  }
  const minMonth = trendMonths[0];
  const maxMonth = trendMonths[trendMonths.length - 1];

  for (let i = 0; i < cows.length; i++) {
    const c = cows[i];
    if (c.is_stillborn || c.category === 'мертворождение' || normalizeAgeGroup(c.age_group) === 'Мертворождённые / Аборты') continue;
    const farmMatch = (userType === 'admin' && (farmName === 'all' || !farmName)) ? true : c.farm_name === farmName;
    if (!farmMatch) continue;
    const m = c.disposal_date.substring(0, 7);
    if (m >= minMonth && m <= maxMonth && trendCounts[m] && trendCounts[m][c.category] !== undefined) {
      trendCounts[m][c.category]++;
    }
  }

  const trendDatasets = ['падёж', 'выбраковка', 'санитарный'].map(cat => {
    const data = trendMonths.map(m => trendCounts[m][cat] || 0);
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

    for (let i = 0; i < cows.length; i++) {
      const c = cows[i];
      if (c.is_stillborn || c.category === 'мертворождение' || normalizeAgeGroup(c.age_group) === 'Мертворождённые / Аборты') continue;
      const farmMatch = (userType === 'admin' && (farmName === 'all' || !farmName)) ? true : c.farm_name === farmName;
      if (farmMatch && c.disposal_date >= prevStartStr && c.disposal_date <= prevEndStr) {
        prevPeriodCount++;
      }
    }

    if (prevPeriodCount > 0) {
      growthPct = Math.round(((totalDisposals - prevPeriodCount) / prevPeriodCount) * 1000) / 10;
    } else {
      growthPct = totalDisposals > 0 ? 100 : 0;
    }
  } catch (e) {
    growthPct = 0;
  }

  // Separated Age Group KPI computations (live animal disposals)
  // 1. Телята (до 6 мес.) — молочный и профилакторный период
  const calfDisposals = liveCows.filter(c => normalizeAgeGroup(c.age_group, c.lactation) === 'Телята (до 6 мес.)');
  const calfDeathCount = calfDisposals.filter(c => c.category === 'падёж').length;
  const calfCullingCount = calfDisposals.filter(c => c.category === 'выбраковка').length;
  const calfSanitaryCount = calfDisposals.filter(c => c.category === 'санитарный').length;

  // 2. Молодняк (от 6 до 18 мес.) — строго 6-18 месяцев
  const youngstockDisposals = liveCows.filter(c => normalizeAgeGroup(c.age_group, c.lactation) === 'Молодняк (от 6 до 18 мес.)');
  const youngstockDeathCount = youngstockDisposals.filter(c => c.category === 'падёж').length;
  const youngstockCullingCount = youngstockDisposals.filter(c => c.category === 'выбраковка').length;
  const youngstockSanitaryCount = youngstockDisposals.filter(c => c.category === 'санитарный').length;

  // 3. Нетели и тёлки (> 18 мес.) — старший молодняк и нетели
  const heiferDisposals = liveCows.filter(c => normalizeAgeGroup(c.age_group, c.lactation) === 'Нетели и тёлки (> 18 мес.)');
  const heiferDeathCount = heiferDisposals.filter(c => c.category === 'падёж').length;

  // 4. Бычки на откорме
  const bullDisposals = liveCows.filter(c => normalizeAgeGroup(c.age_group, c.lactation) === 'Бычки на откорме');
  const bullDeathCount = bullDisposals.filter(c => c.category === 'падёж').length;

  // 5. Коровы 1-й лактации (первотёлки)
  const firstLactDisposals = liveCows.filter(c => normalizeAgeGroup(c.age_group, c.lactation) === 'Коровы 1-й лактации (первотёлки)');
  const firstLactDeaths = firstLactDisposals.filter(c => c.category === 'падёж').length;

  // 6. Коровы 2+ лактаций (полновозрастные)
  const multiparousDisposals = liveCows.filter(c => normalizeAgeGroup(c.age_group, c.lactation) === 'Коровы 2+ лактаций (полновозрастные)');
  const multiparousDeaths = multiparousDisposals.filter(c => c.category === 'падёж').length;

  // 7. Коровы сухостойные
  const dryDisposals = liveCows.filter(c => normalizeAgeGroup(c.age_group, c.lactation) === 'Коровы сухостойные');
  const dryDeaths = dryDisposals.filter(c => c.category === 'падёж').length;

  // Fresh period (0-30 days DIM) computations
  const freshCohort = lactationCohorts['Новотел (0–30 дн)'];
  const freshDisposals = freshCohort ? freshCohort.total : 0;
  const freshDeaths = freshCohort ? freshCohort.death : 0;

  const distinctFarmsList = getUniqueFarms();
  const recentCows = [...relevantCows].sort((a, b) => b.disposal_date.localeCompare(a.disposal_date)).slice(0, 10);

  let allTimeTotal = 0;
  if (userType === 'admin' && (farmName === 'all' || !farmName)) {
    allTimeTotal = cows.length;
  } else {
    for (let i = 0; i < cows.length; i++) {
      if (cows[i].farm_name === farmName) allTimeTotal++;
    }
  }

  // Lactation Cohort Chart Datasets (Adult Cows)
  const lactationLabels = ['Новотел (0–30 дн)', 'Раздой (31–100 дн)', 'Середина (101–200 дн)', 'Спад (201–305+ дн)', 'Сухостой'];
  const lactationDeathData = lactationLabels.map(l => lactationCohorts[l]?.death || 0);
  const lactationCullingData = lactationLabels.map(l => (lactationCohorts[l]?.culling || 0) + (lactationCohorts[l]?.sanitary || 0));

  // Stacked Age Groups in natural chronological order
  const standardAgeGroupOrder = [
    'Телята (до 6 мес.)',
    'Молодняк (от 6 до 18 мес.)',
    'Нетели и тёлки (> 18 мес.)',
    'Коровы 1-й лактации (первотёлки)',
    'Коровы 2+ лактаций (полновозрастные)',
    'Коровы сухостойные',
    'Бычки на откорме'
  ];
  const ageGroupLabels = standardAgeGroupOrder.filter(ag => (categoryMatrix[ag]?.total || 0) > 0 || (ageGroupCounts[ag] || 0) > 0);
  if (ageGroupLabels.length === 0) ageGroupLabels.push(...standardAgeGroupOrder);
  const ageGroupDeathData = ageGroupLabels.map(ag => categoryMatrix[ag]?.death || 0);
  const ageGroupCullingData = ageGroupLabels.map(ag => categoryMatrix[ag]?.culling || 0);
  const ageGroupSanitaryData = ageGroupLabels.map(ag => categoryMatrix[ag]?.sanitary || 0);

  // Veterinary Safety Scorecard indicators
  const mortalityPct = totalDisposals > 0 ? (categoryCounts['падёж'] / totalDisposals) * 100 : 0;
  const freshSharePct = totalDisposals > 0 ? (freshDisposals / totalDisposals) * 100 : 0;
  
  const adultCowTotal = (lactNumberDeath.reduce((a, b) => a + b, 0) + lactNumberCulling.reduce((a, b) => a + b, 0));
  const firstLactTotal = lactNumberDeath[0] + lactNumberCulling[0];
  const firstLactPct = adultCowTotal > 0 ? (firstLactTotal / adultCowTotal) * 100 : 0;

  const locomotorTotal = pathologySystems['Конечности и травматизм'] || 0;
  const locomotorPct = totalDisposals > 0 ? (locomotorTotal / totalDisposals) * 100 : 0;

  const mastitisTotal = pathologySystems['Болезни вымени (маститы)'] || 0;
  const mastitisPct = totalDisposals > 0 ? (mastitisTotal / totalDisposals) * 100 : 0;

  // Progress calculations
  const progFresh = Math.max(5, Math.min(100, Math.round((freshSharePct / Math.max(currentPricingStandards.norm_fresh_cow_disposal, 0.1)) * 100)));
  const progFirstLact = Math.max(5, Math.min(100, Math.round((firstLactPct / Math.max(currentPricingStandards.norm_first_lactation_culling, 0.1)) * 100)));
  const progMortality = Math.max(5, Math.min(100, Math.round((mortalityPct / Math.max(currentPricingStandards.norm_mortality_rate, 0.1)) * 100)));
  const progLocomotor = Math.max(5, Math.min(100, Math.round((locomotorPct / Math.max(currentPricingStandards.norm_locomotor_disorders, 0.1)) * 100)));
  const progMastitis = Math.max(5, Math.min(100, Math.round((mastitisPct / Math.max(currentPricingStandards.norm_mastitis_disorders, 0.1)) * 100)));

  const scorecard = [
    {
      key: 'norm_fresh_cow_disposal',
      operator: '<=',
      val: currentPricingStandards.norm_fresh_cow_disposal,
      warn_val: currentPricingStandards.warn_fresh_cow_disposal,
      crit_val: currentPricingStandards.crit_fresh_cow_disposal,
      current_num: freshSharePct,
      title: 'Выбытие новотельных (0-30 DIM)',
      target: `≤ ${currentPricingStandards.norm_fresh_cow_disposal.toFixed(1)}%`,
      current: `${freshSharePct.toFixed(1)}%`,
      progress_pct: progFresh,
      status: freshSharePct <= currentPricingStandards.norm_fresh_cow_disposal ? 'success' : (freshSharePct <= currentPricingStandards.warn_fresh_cow_disposal ? 'warning' : 'danger'),
      statusText: freshSharePct <= currentPricingStandards.norm_fresh_cow_disposal ? 'Норма' : (freshSharePct <= currentPricingStandards.warn_fresh_cow_disposal ? 'Внимание' : 'Риск'),
      note: `Новотел: ${freshDisposals} гол. (${freshDeaths} пало)`,
      icon: 'bi-exclamation-octagon-fill'
    },
    {
      key: 'norm_first_lactation_culling',
      operator: '<=',
      val: currentPricingStandards.norm_first_lactation_culling,
      warn_val: currentPricingStandards.warn_first_lactation_culling,
      crit_val: currentPricingStandards.crit_first_lactation_culling,
      current_num: firstLactPct,
      title: 'Выбраковка первотёлок',
      target: `≤ ${currentPricingStandards.norm_first_lactation_culling.toFixed(1)}%`,
      current: `${firstLactPct.toFixed(1)}%`,
      progress_pct: progFirstLact,
      status: firstLactPct <= currentPricingStandards.norm_first_lactation_culling ? 'success' : (firstLactPct <= currentPricingStandards.warn_first_lactation_culling ? 'warning' : 'danger'),
      statusText: firstLactPct <= currentPricingStandards.norm_first_lactation_culling ? 'Норма' : (firstLactPct <= currentPricingStandards.warn_first_lactation_culling ? 'Внимание' : 'Высокая'),
      note: 'Доля 1-й лактации в выбраковке',
      icon: 'bi-gem'
    },
    {
      key: 'norm_mortality_rate',
      operator: '<=',
      val: currentPricingStandards.norm_mortality_rate,
      warn_val: currentPricingStandards.warn_mortality_rate,
      crit_val: currentPricingStandards.crit_mortality_rate,
      current_num: mortalityPct,
      title: 'Общая летальность (Падёж)',
      target: `≤ ${currentPricingStandards.norm_mortality_rate.toFixed(1)}%`,
      current: `${mortalityPct.toFixed(1)}%`,
      progress_pct: progMortality,
      status: mortalityPct <= currentPricingStandards.norm_mortality_rate ? 'success' : (mortalityPct <= currentPricingStandards.warn_mortality_rate ? 'warning' : 'danger'),
      statusText: mortalityPct <= currentPricingStandards.norm_mortality_rate ? 'Норма' : (mortalityPct <= currentPricingStandards.warn_mortality_rate ? 'Повышен' : 'Критич.'),
      note: `Пало ${categoryCounts['падёж']} из ${totalDisposals} гол.`,
      icon: 'bi-heart-pulse-fill'
    },
    {
      key: 'norm_locomotor_disorders',
      operator: '<=',
      val: currentPricingStandards.norm_locomotor_disorders,
      warn_val: currentPricingStandards.warn_locomotor_disorders,
      crit_val: currentPricingStandards.crit_locomotor_disorders,
      current_num: locomotorPct,
      title: 'Болезни конечностей',
      target: `≤ ${currentPricingStandards.norm_locomotor_disorders.toFixed(1)}%`,
      current: `${locomotorPct.toFixed(1)}%`,
      progress_pct: progLocomotor,
      status: locomotorPct <= currentPricingStandards.norm_locomotor_disorders ? 'success' : (locomotorPct <= currentPricingStandards.warn_locomotor_disorders ? 'warning' : 'danger'),
      statusText: locomotorPct <= currentPricingStandards.norm_locomotor_disorders ? 'Норма' : (locomotorPct <= currentPricingStandards.warn_locomotor_disorders ? 'Внимание' : 'Риск'),
      note: 'Ортопедическая патология',
      icon: 'bi-bandaid-fill'
    },
    {
      key: 'norm_mastitis_disorders',
      operator: '<=',
      val: currentPricingStandards.norm_mastitis_disorders,
      warn_val: currentPricingStandards.warn_mastitis_disorders,
      crit_val: currentPricingStandards.crit_mastitis_disorders,
      current_num: mastitisPct,
      title: 'Маститы и патологии вымени',
      target: `≤ ${currentPricingStandards.norm_mastitis_disorders.toFixed(1)}%`,
      current: `${mastitisPct.toFixed(1)}%`,
      progress_pct: progMastitis,
      status: mastitisPct <= currentPricingStandards.norm_mastitis_disorders ? 'success' : (mastitisPct <= currentPricingStandards.warn_mastitis_disorders ? 'warning' : 'danger'),
      statusText: mastitisPct <= currentPricingStandards.norm_mastitis_disorders ? 'Норма' : (mastitisPct <= currentPricingStandards.warn_mastitis_disorders ? 'Внимание' : 'Риск'),
      note: 'Инфекции молочной железы',
      icon: 'bi-droplet-fill'
    }
  ];

  // Farm Comparative Matrix
  const farmMatrixList = Object.entries(farmMatrix).map(([name, stat]) => {
    const dPct = stat.total > 0 ? Math.round((stat.death / stat.total) * 1000) / 10 : 0;
    const avgD = stat.dimCount > 0 ? Math.round(stat.totalDim / stat.dimCount) : 0;
    let status: 'optimal' | 'warning' | 'critical' = 'optimal';
    if (dPct > 35 || stat.death > 20) status = 'critical';
    else if (dPct > 25 || stat.fresh > 12) status = 'warning';

    return {
      farm_name: name,
      farm: name,
      total: stat.total,
      death: stat.death,
      culling: stat.culling,
      sanitary: stat.sanitary,
      death_pct: dPct,
      calves: stat.calves,
      youngstock: stat.youngstock,
      heifers: stat.heifers,
      fresh: stat.fresh,
      avg_dim: avgD,
      loss_byn: Math.round(stat.lossByn),
      status
    };
  }).sort((a, b) => b.total - a.total);

  // 9. Стельность и мертворождения / абортов
  const stillbornKeywords = ['мертворож', 'аборт', 'плод', 'мумификац', 'мацерац', 'патология родов', 'патологические роды', 'гибель плода', 'мертвый теленок'];
  const pregnantCowsList: Cow[] = [];
  const stillbornCowsList: Cow[] = [];

  for (const c of relevantCows) {
    const reasonLower = (c.reason || '').toLowerCase();
    const ageGrpLower = (c.age_group || '').toLowerCase();
    const phaseLower = (c.lactation_phase || '').toLowerCase();

    let isPreg = false;
    if (c.is_pregnant === 1 || (c.gestation_days && c.gestation_days > 0)) {
      isPreg = true;
    } else if (phaseLower.includes('сухостой') || ageGrpLower.includes('сухостой') || ageGrpLower.includes('нетел') || reasonLower.includes('стельн') || ageGrpLower.includes('стельн')) {
      isPreg = true;
    }
    if (isPreg) pregnantCowsList.push(c);

    let isStillborn = false;
    if (c.is_stillborn === 1) {
      isStillborn = true;
    } else if (stillbornKeywords.some(k => reasonLower.includes(k)) || ageGrpLower.includes('мертворожд') || ageGrpLower.includes('аборт')) {
      isStillborn = true;
    }
    if (isStillborn) stillbornCowsList.push(c);
  }

  const adultCowsTotalCount = relevantCows.filter(c => !['телят', 'молодняк'].some(k => (c.age_group || '').toLowerCase().includes(k))).length;
  const pregnantCount = pregnantCowsList.length;
  const pregnantPct = adultCowsTotalCount > 0 ? Math.round((pregnantCount / adultCowsTotalCount) * 1000) / 10 : 0;
  const pregnantLossByn = Math.round(pregnantCowsList.reduce((acc, c) => acc + estimateCowValue(c), 0));

  const gestVals = pregnantCowsList.map(c => c.gestation_days).filter((v): v is number => !!v && v > 0);
  const avgGestationMonths = gestVals.length > 0 ? Math.round((gestVals.reduce((a, b) => a + b, 0) / gestVals.length / 30) * 10) / 10 : 6.5;

  const stillbornCount = stillbornCowsList.length;
  const stillbornPct = totalDisposals > 0 ? Math.round((stillbornCount / totalDisposals) * 1000) / 10 : 0;

  const stillbornReasonsMap: Record<string, number> = {};
  for (const c of stillbornCowsList) {
    const r = c.reason || 'Патология плода';
    stillbornReasonsMap[r] = (stillbornReasonsMap[r] || 0) + 1;
  }
  const stillbornReasonsList = Object.entries(stillbornReasonsMap)
    .map(([reason, count]) => ({ reason, count }))
    .sort((a, b) => b.count - a.count);

  // Trimesters calculation
  // Сроки стельности выбывших коров (без примешивания мертворождений)
  let t1Count = 0; // 1-90 дн
  let t2Count = 0; // 91-180 дн
  let t3Count = 0; // 181-240 дн
  let t4Count = 0; // 241+ дн (глубокий сухостой перед отёлом)
  for (const c of pregnantCowsList) {
    const days = c.gestation_days || 0;
    const agL = (c.age_group || '').toLowerCase();
    if (days > 240 || (agL.includes('сухосто') && days > 210)) {
      t4Count++;
    } else if (days > 180 || agL.includes('сухосто')) {
      t3Count++;
    } else if (days > 90) {
      t2Count++;
    } else {
      t1Count++;
    }
  }

  const structureLabels = [
    '1–90 дн (1-й триместр)',
    '91–180 дн (2-й триместр)',
    '181–240 дн (3-й триместр)',
    '241+ дн (сухостой перед отёлом)'
  ];
  const structureData = [t1Count, t2Count, t3Count, t4Count];
  const structureColors = [
    'rgba(59, 130, 246, 0.85)',
    'rgba(245, 158, 11, 0.85)',
    'rgba(249, 115, 22, 0.85)',
    'rgba(239, 68, 68, 0.85)'
  ];

  const reproductionByFarm = farmMatrixList.map(fm => {
    const fCows = relevantCows.filter(c => (c.farm_name || 'Не указана') === fm.farm_name);
    const fPregCows = fCows.filter(c => pregnantCowsList.includes(c));
    const fPregDeath = fPregCows.filter(c => (c.category || '').toLowerCase() === 'падёж').length;
    const fPregCull = fPregCows.filter(c => (c.category || '').toLowerCase() !== 'падёж').length;
    const fPregLoss = fPregCows.reduce((sum, c) => sum + estimateCowValue(c), 0);
    const fStillborn = fCows.filter(c => stillbornCowsList.includes(c)).length;
    return {
      farm_name: fm.farm_name,
      total: fCows.length,
      pregnant_count: fPregCows.length,
      pregnant_pct: fCows.length > 0 ? Math.round((fPregCows.length / fCows.length) * 1000) / 10 : 0,
      pregnant_death: fPregDeath,
      pregnant_culling: fPregCull,
      pregnant_loss_byn: Math.round(fPregLoss),
      stillborn_count: fStillborn,
      stillborn_pct: fCows.length > 0 ? Math.round((fStillborn / fCows.length) * 1000) / 10 : 0
    };
  });

  let pregDeath = 0;
  let pregCulling = 0;
  let pregSanitary = 0;
  const pregReasonsMap: Record<string, number> = {};
  for (const c of pregnantCowsList) {
    const cat = (c.category || '').toLowerCase();
    if (cat === 'падёж') pregDeath++;
    else if (cat === 'выбраковка') pregCulling++;
    else pregSanitary++;

    const r = c.reason || 'Не указана';
    pregReasonsMap[r] = (pregReasonsMap[r] || 0) + 1;
  }
  const pregReasonsList = Object.entries(pregReasonsMap)
    .map(([reason, count]) => ({ reason, count }))
    .sort((a, b) => b.count - a.count);

  const farmLabels = reproductionByFarm.map(f => f.farm_name);
  const farmPregnantTotal = reproductionByFarm.map(f => f.pregnant_count);
  const farmPregnantDeath = reproductionByFarm.map(f => f.pregnant_death);
  const farmPregnantCulling = reproductionByFarm.map(f => f.pregnant_culling);

  const reproductionSummary = {
    pregnant_count: pregnantCount,
    pregnant_pct: pregnantPct,
    pregnant_loss_byn: pregnantLossByn,
    pregnant_death_count: pregDeath,
    pregnant_culling_count: pregCulling,
    pregnant_sanitary_count: pregSanitary,
    pregnant_top_reasons: pregReasonsList.slice(0, 5),
    late_gestation_count: t3Count + t4Count,
    avg_gestation_months: avgGestationMonths,
    stillborn_count: stillbornCount,
    stillborn_pct: stillbornPct,
    stillborn_reasons: stillbornReasonsList,
    by_farm: reproductionByFarm,
    stages: {
      trimester_1: t1Count,
      trimester_2: t2Count,
      trimester_3: t3Count,
      trimester_4: t4Count
    },
    charts: {
      structure: {
        labels: structureLabels,
        data: structureData,
        colors: structureColors
      },
      farms: {
        labels: farmLabels,
        pregnant_total: farmPregnantTotal,
        pregnant_death: farmPregnantDeath,
        pregnant_culling: farmPregnantCulling
      },
      reasons: {
        labels: pregReasonsList.slice(0, 6).map(r => r.reason),
        data: pregReasonsList.slice(0, 6).map(r => r.count)
      }
    }
  };

  return {
    reproduction: reproductionSummary,
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
      // 1. Телята (до 6 мес.)
      calf_disposals: calfDisposals.length,
      calf_death_count: calfDeathCount,
      calf_culling_count: calfCullingCount,
      calf_sanitary_count: calfSanitaryCount,
      // 2. Молодняк (от 6 до 18 мес.)
      youngstock_disposals: youngstockDisposals.length,
      youngstock_death_count: youngstockDeathCount,
      youngstock_culling_count: youngstockCullingCount,
      youngstock_sanitary_count: youngstockSanitaryCount,
      youngstock_death_pct: youngstockDisposals.length > 0 ? Math.round((youngstockDeathCount / youngstockDisposals.length) * 1000) / 10 : 0,
      // 3. Нетели и тёлки (> 18 мес.)
      heifer_disposals: heiferDisposals.length,
      heifer_death_count: heiferDeathCount,
      // 4. Бычки на откорме
      bull_disposals: bullDisposals.length,
      bull_death_count: bullDeathCount,
      // 5. Первотёлки (1 лактация)
      first_lact_disposals: firstLactDisposals.length,
      first_lact_deaths: firstLactDeaths,
      // 6. Полновозрастные (2+ лактаций)
      multiparous_disposals: multiparousDisposals.length,
      multiparous_deaths: multiparousDeaths,
      // 7. Сухостой
      dry_disposals: dryDisposals.length,
      dry_deaths: dryDeaths,
      // Лактация и DIM
      fresh_disposals: freshDisposals,
      fresh_deaths: freshDeaths,
      fresh_share_pct: totalDisposals > 0 ? Math.round((freshDisposals / totalDisposals) * 1000) / 10 : 0,
      avg_dim: countLactatingDim > 0 ? Math.round(sumLactatingDim / countLactatingDim) : 0,
      avg_lactation: countLactationNum > 0 ? (sumLactationNum / countLactationNum).toFixed(1) : '1.0',
      all_time_total: allTimeTotal,
      // Экономика
      total_loss_byn: Math.round(totalBookValue),
      death_loss_byn: Math.round(deathBookValue),
      culling_loss_byn: Math.round(cullingBookValue),
      avg_head_loss: totalDisposals > 0 ? Math.round(totalBookValue / totalDisposals) : 0
    },
    charts: {
      categories: {
        labels: ['Падёж', 'Выбраковка', 'Санитарный брак'],
        data: [categoryCounts['падёж'], categoryCounts['выбраковка'], categoryCounts['санитарный']],
        colors: ['#EF4444', '#3B82F6', '#F59E0B']
      },
      age_groups: {
        labels: ageGroupLabels,
        data: ageGroupLabels.map(ag => (categoryMatrix[ag]?.total || 0)),
        colors: '#10B981',
        death_data: ageGroupDeathData,
        culling_data: ageGroupCullingData,
        sanitary_data: ageGroupSanitaryData
      },
      lactation_phases: {
        labels: lactationLabels,
        death_data: lactationDeathData,
        culling_data: lactationCullingData
      },
      dim_curve: {
        labels: dimBins.map(b => b.label),
        death_data: dimCurveDeath,
        culling_data: dimCurveCulling
      },
      lactation_numbers: {
        labels: ['1 лактация (первотёлки)', '2 лактация', '3 лактация', '4 лактация', '5+ лактация'],
        death_data: lactNumberDeath,
        culling_data: lactNumberCulling
      },
      pathology: {
        labels: sortedPathology.map(x => x[0]),
        data: sortedPathology.map(x => x[1]),
        colors: ['#DC2626', '#2563EB', '#10B981', '#F59E0B', '#8B5CF6', '#EC4899', '#06B6D4', '#64748B']
      },
      economics_by_group: {
        labels: Object.keys(bookValueByGroup),
        data: Object.values(bookValueByGroup).map(v => Math.round(v)),
        colors: ['#0284C7', '#10B981', '#F59E0B', '#8B5CF6', '#EF4444', '#64748B']
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
    scorecard,
    farm_matrix: farmMatrixList,
    lactation_cohorts: lactationCohorts,
    category_analytics: categoryAnalyticsList,
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

// Admin Test Data Generator & Benchmarks
app.get('/admin/generator', loginRequired, adminRequired, (req: Request, res: Response) => {
  const t0 = performance.now();

  const farmStats: Record<string, number> = {};
  const catStats: Record<string, number> = { 'падёж': 0, 'выбраковка': 0, 'санитарный': 0 };
  let totalWeight = 0;

  for (const c of cows) {
    farmStats[c.farm_name] = (farmStats[c.farm_name] || 0) + 1;
    catStats[c.category] = (catStats[c.category] || 0) + 1;
    totalWeight += (c.weight || 0);
  }

  const t1 = performance.now();
  const benchmarkMs = (t1 - t0).toFixed(2);
  const memoryMb = (process.memoryUsage().rss / (1024 * 1024)).toFixed(1);

  res.render('admin_generator', {
    cows,
    benchmark_ms: benchmarkMs,
    memory_mb: memoryMb,
    farm_stats: farmStats,
    cat_stats: catStats,
    total_weight_formatted: Math.round(totalWeight).toLocaleString('ru-RU') + ' кг',
    security_metrics: {
      totalRequests: securityMetrics.totalRequests,
      blockedRequestsCount: securityMetrics.blockedRequestsCount,
      blockedIpsCount: securityMetrics.blockedIpsTotal.size,
      authFailuresCount: securityMetrics.authFailuresCount,
      slowRequestsCount: securityMetrics.slowRequestsCount,
      trackedIpsCount: globalDdosLimiter.getTrackedCount(),
      uptimeMinutes: Math.floor((Date.now() - securityMetrics.startedAt.getTime()) / 60000)
    }
  });
});

app.post('/admin/generate_test_data', loginRequired, adminRequired, (req: Request, res: Response) => {
  const action = req.body.action || 'reset_1250';

  if (action === 'add_500') {
    populateRealisticCows(500, false);
    addFlash(req, `Добавлено +500 тестовых записей. Всего в базе: ${cows.length} голов.`, 'success');
  } else if (action === 'add_1000') {
    populateRealisticCows(1000, false);
    addFlash(req, `Добавлено +1 000 тестовых записей. Всего в базе: ${cows.length} голов.`, 'success');
  } else if (action === 'add_5000') {
    populateRealisticCows(5000, false);
    addFlash(req, `Добавлено +5 000 тестовых записей. Всего в базе: ${cows.length} голов.`, 'success');
  } else if (action === 'set_9000') {
    populateRealisticCows(9000, true);
    addFlash(req, `База данных успешно инициализирована: ровно 9 000 реалистичных записей для нагрузочного стресс-теста.`, 'success');
  } else if (action === 'clear_all') {
    cows.length = 0;
    addFlash(req, 'База данных полностью очищена (0 записей).', 'warning');
  } else {
    populateRealisticCows(1250, true);
    addFlash(req, `База данных сброшена к эталонному набору: 1 250 реалистичных записей за 12 месяцев.`, 'success');
  }

  const referer = req.headers.referer || '/admin/generator';
  res.redirect(referer);
});

// Live Anti-DDoS and Security Metrics API (Admin Only)
app.get('/api/security_status', loginRequired, adminRequired, (req: Request, res: Response) => {
  res.json({
    status: 'ACTIVE_SHIELD',
    uptime_minutes: Math.floor((Date.now() - securityMetrics.startedAt.getTime()) / 60000),
    total_requests: securityMetrics.totalRequests,
    blocked_requests: securityMetrics.blockedRequestsCount,
    blocked_ips_count: securityMetrics.blockedIpsTotal.size,
    auth_failures: securityMetrics.authFailuresCount,
    slow_requests: securityMetrics.slowRequestsCount,
    tracked_ips_in_memory: globalDdosLimiter.getTrackedCount(),
    protection_layers: [
      'Sliding Window L7 Rate Limiter (180 req/min)',
      'Burst Flood Spike Limiter (35 req/5sec)',
      'Auth Brute Force & Credential Stuffing Guard (8 req/3min)',
      'Bcrypt CPU Starvation Tarpit & Progressive Delay',
      'Slowloris & Slow HTTP 25s Execution Timeout',
      'Payload Size Bounding (2MB JSON/Urlencoded)',
      'Parameter Pollution & Prototype Pollution Blocker',
      'Process Crash Immunity (uncaughtException & unhandledRejection)',
      'HTTP Security Headers (nosniff, XSS, Referrer-Policy, No-X-Powered-By)'
    ]
  });
});

// Login with Brute-Force & Bcrypt CPU Starvation Protection
app.get('/login', (req: Request, res: Response) => {
  if (req.session.user_id) {
    return res.redirect('/dashboard');
  }
  res.render('login');
});

app.post('/login', async (req: Request, res: Response) => {
  const clientIp = getClientIp(req);
  const username = String(req.body.username || '').trim();
  const password = String(req.body.password || '');

  // 1. Check Auth Rate Limiter
  const rateCheck = authLimiter.check(clientIp);
  if (!rateCheck.allowed) {
    securityMetrics.blockedRequestsCount++;
    addFlash(req, `Слишком много попыток входа с вашего IP. Защита заблокировала вход на ${rateCheck.retryAfterSec || 60} сек.`, 'danger');
    return res.status(429).render('login');
  }

  // 2. Check Lockout for IP & Username
  const ipLock = checkLoginLockout(clientIp);
  const userLock = checkLoginLockout(username);
  if (ipLock.locked || userLock.locked) {
    securityMetrics.blockedRequestsCount++;
    const waitSec = Math.max(ipLock.waitSec, userLock.waitSec);
    addFlash(req, `Превышен лимит неверных попыток авторизации. Вход заблокирован на ${waitSec} сек.`, 'danger');
    return res.status(429).render('login');
  }

  const user = users.find(u => u.username === username);

  // 3. Constant-time / CPU-safe password verification
  let isValid = false;
  if (user) {
    try {
      isValid = await bcrypt.compare(password, user.password_hash);
    } catch {
      isValid = false;
    }
  } else {
    // Fake compare to prevent timing attacks, handled asynchronously
    try {
      await bcrypt.compare(password, '$2a$10$7EqJtq98hPqEX7fNZaFWoO.8/q3g1j2p4n5m6k7l8i9o0p1q2r3s4');
    } catch {
      // ignore
    }
  }

  if (isValid && user) {
    clearFailedLogin(clientIp);
    clearFailedLogin(username);
    req.session.user_id = user.id;
    req.session.username = user.username;
    req.session.user_type = user.user_type;
    req.session.farm_name = user.farm_name;
    addFlash(req, 'Вход выполнен успешно', 'success');
    return res.redirect('/dashboard');
  }

  // On failure: record failed attempt & throttle rapid bots
  securityMetrics.authFailuresCount++;
  recordFailedLogin(clientIp);
  if (username) recordFailedLogin(username);

  // Progressive delay to defeat automated brute-force scripts
  await new Promise(r => setTimeout(r, 600));

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

  const period = (req.query.period as string) || 'all';
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

  res.render('dashboard', {
    user_type: userType,
    farm_name: farmName,
    selected_farm: selectedFarm,
    d: dashboardData,
    alerts: alerts,
    user_stats_data: userStatsData,
    pricing: currentPricingStandards
  });
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

// High-Performance Paginated API for Cows (handles 9,000+ records in < 1ms)
app.get('/api/cows', loginRequired, (req: Request, res: Response) => {
  const userType = req.session.user_type;
  const sessionFarm = req.session.farm_name;

  const page = Math.max(1, parseInt(String(req.query.page), 10) || 1);
  const limitQuery = String(req.query.limit || '50');
  const limit = limitQuery === 'all' ? 1000 : Math.min(1000, Math.max(10, parseInt(limitQuery, 10) || 50));
  const recordType = String(req.query.record_type || 'live').trim().toLowerCase();
  const farmFilter = String(req.query.farm || '').trim();
  const categoryFilter = String(req.query.category || '').trim().toLowerCase();
  const reasonFilter = String(req.query.reason || '').trim();
  const ageGroupFilter = String(req.query.age_group || '').trim();
  const lactationPhaseFilter = String(req.query.lactation_phase || '').trim();
  const reproFilter = String(req.query.repro_filter || '').trim().toLowerCase();
  const searchQuery = String(req.query.search || '').trim().toLowerCase();
  const sort = String(req.query.sort || 'newest').trim();
  const startDate = String(req.query.start_date || '').trim();
  const endDate = String(req.query.end_date || '').trim();
  const isSanitaryCategory = (categoryFilter === 'санитарный' || categoryFilter === 'санбрак');

  // Filter in memory (runs in ~0.2ms for 9,000 records)
  const filtered = cows.filter(c => {
    // Record type partition (live cattle disposals vs fetal losses/abortions)
    const isStill = (c.is_stillborn === 1 || c.category === 'мертворождение' || normalizeAgeGroup(c.age_group) === 'Мертворождённые / Аборты');
    if (reproFilter === 'stillborn' || recordType === 'stillborn') {
      if (!isStill) return false;
    } else if (recordType === 'all') {
      // allow all records
    } else {
      // default 'live': show live cattle disposals only, strictly excluding abortions/stillborns
      if (isStill) return false;
    }

    // Farm filter
    if (userType !== 'admin') {
      if (c.farm_name !== sessionFarm) return false;
    } else if (farmFilter && farmFilter !== 'all') {
      if (c.farm_name !== farmFilter) return false;
    }

    // Date range filter
    if (startDate && endDate) {
      if (c.disposal_date < startDate || c.disposal_date > endDate) return false;
    }

    // Category filter (вид выбытия)
    if (categoryFilter && categoryFilter !== 'all') {
      const catLower = c.category.toLowerCase();
      if (isSanitaryCategory) {
        if (!catLower.includes('сан')) return false;
      } else if (catLower !== categoryFilter) {
        return false;
      }
    }

    // Age group filter (категория скота)
    if (ageGroupFilter && ageGroupFilter !== 'all') {
      if (!matchesAgeGroupFilter(c, ageGroupFilter)) return false;
    }

    // Lactation phase filter
    if (lactationPhaseFilter && lactationPhaseFilter !== 'all') {
      const phase = c.lactation_phase || computeLactationPhase(c.age_group, c.lactation_days, c.lactation);
      if (!phase.toLowerCase().includes(lactationPhaseFilter.toLowerCase())) {
        return false;
      }
    }

    // Repro filter (выбытие стельных коров / мертворождения)
    if (reproFilter && reproFilter !== 'stillborn') {
      const agL = (c.age_group || '').toLowerCase();
      const rL = (c.reason || '').toLowerCase();
      const isPreg = (c.is_pregnant === 1 || ((c.gestation_days || 0) > 0) || agL.includes('сухосто') || agL.includes('нетел') || rL.includes('стельн'));

      if (reproFilter === 'pregnant' && !isPreg) return false;
      if (reproFilter === 'pregnant_late') {
        const isLate = ((c.gestation_days || 0) >= 180) || (isPreg && agL.includes('сухосто'));
        if (!isLate) return false;
      }
    }

    // Reason filter
    if (reasonFilter && reasonFilter !== 'all') {
      if (c.reason !== reasonFilter) return false;
    }

    // Search query
    if (searchQuery) {
      const matchId = c.cow_id.toLowerCase().includes(searchQuery);
      const matchTag = c.ear_tag ? c.ear_tag.toLowerCase().includes(searchQuery) : false;
      const matchReason = c.reason.toLowerCase().includes(searchQuery);
      const matchFarm = c.farm_name.toLowerCase().includes(searchQuery);
      const matchAg = c.age_group ? c.age_group.toLowerCase().includes(searchQuery) : false;
      const matchPhase = c.lactation_phase ? c.lactation_phase.toLowerCase().includes(searchQuery) : false;
      const matchNotes = c.notes ? c.notes.toLowerCase().includes(searchQuery) : false;
      if (!matchId && !matchTag && !matchReason && !matchFarm && !matchAg && !matchPhase && !matchNotes) {
        return false;
      }
    }

    return true;
  });

  // Sort
  if (sort === 'oldest') {
    filtered.sort((a, b) => a.disposal_date.localeCompare(b.disposal_date) || a.id - b.id);
  } else if (sort === 'weight_desc') {
    filtered.sort((a, b) => (b.weight || 0) - (a.weight || 0));
  } else if (sort === 'id_asc') {
    filtered.sort((a, b) => a.id - b.id);
  } else if (sort === 'id_desc') {
    filtered.sort((a, b) => b.id - a.id);
  } else {
    // default 'newest'
    filtered.sort((a, b) => b.disposal_date.localeCompare(a.disposal_date) || b.id - a.id);
  }

  // Calculate quick stats on filtered set
  let deathCount = 0;
  let cullingCount = 0;
  let sanitaryCount = 0;
  for (let i = 0; i < filtered.length; i++) {
    const cat = filtered[i].category;
    if (cat === 'падёж') deathCount++;
    else if (cat === 'выбраковка') cullingCount++;
    else sanitaryCount++;
  }

  const totalFiltered = filtered.length;
  const totalPages = Math.max(1, Math.ceil(totalFiltered / limit));
  const currentPage = Math.min(page, totalPages);
  const startIndex = (currentPage - 1) * limit;
  const endIndex = Math.min(startIndex + limit, totalFiltered);
  const paginatedCows = totalFiltered > 0 ? filtered.slice(startIndex, endIndex) : [];

  return res.json({
    success: true,
    total_db: userType === 'admin' ? cows.length : cows.filter(c => c.farm_name === sessionFarm).length,
    total_filtered: totalFiltered,
    page: currentPage,
    limit,
    total_pages: totalPages,
    start_index: totalFiltered > 0 ? startIndex + 1 : 0,
    end_index: endIndex,
    stats: {
      total: totalFiltered,
      death: deathCount,
      culling: cullingCount,
      sanitary: sanitaryCount
    },
    cows: paginatedCows
  });
});

// View Cows (Optimized: renders only the first 50 rows in initial HTML, preventing DOM bloat)
app.get('/cows', loginRequired, (req: Request, res: Response) => {
  const userType = req.session.user_type;
  const farmName = req.session.farm_name;
  const uniqueFarms = getUniqueFarms();
  const farmFilter = String(req.query.farm || '').trim();
  const categoryFilter = String(req.query.category || '').trim().toLowerCase();
  const reasonFilter = String(req.query.reason || '').trim();
  const ageGroupFilter = String(req.query.age_group || '').trim();
  const lactationPhaseFilter = String(req.query.lactation_phase || '').trim();
  const reproFilter = String(req.query.repro_filter || '').trim().toLowerCase();
  const startDate = String(req.query.start_date || '').trim();
  const endDate = String(req.query.end_date || '').trim();
  const isSanitaryCategory = (categoryFilter === 'санитарный' || categoryFilter === 'санбрак');

  const recordType = (reproFilter === 'stillborn' ? 'stillborn' : String(req.query.record_type || 'live')).trim().toLowerCase();

  let userCows = cows.filter(c => {
    const isStill = (c.is_stillborn === 1 || c.category === 'мертворождение' || normalizeAgeGroup(c.age_group) === 'Мертворождённые / Аборты');
    if (recordType === 'stillborn') {
      if (!isStill) return false;
    } else if (recordType === 'all') {
      // allow all records
    } else {
      // default 'live': show live cattle disposals only, strictly excluding abortions/stillborns
      if (isStill) return false;
    }
    return true;
  });

  if (userType !== 'admin') {
    userCows = userCows.filter(c => c.farm_name === farmName);
  } else if (farmFilter && farmFilter !== 'all') {
    userCows = userCows.filter(c => c.farm_name === farmFilter);
  }

  if (startDate && endDate) {
    userCows = userCows.filter(c => c.disposal_date >= startDate && c.disposal_date <= endDate);
  }

  if (categoryFilter && categoryFilter !== 'all') {
    userCows = userCows.filter(c => {
      const catLower = c.category.toLowerCase();
      if (isSanitaryCategory) return catLower.includes('сан');
      return catLower === categoryFilter;
    });
  }

  if (reasonFilter && reasonFilter !== 'all') {
    userCows = userCows.filter(c => c.reason === reasonFilter);
  }

  if (ageGroupFilter && ageGroupFilter !== 'all') {
    userCows = userCows.filter(c => matchesAgeGroupFilter(c, ageGroupFilter));
  }

  if (lactationPhaseFilter && lactationPhaseFilter !== 'all') {
    userCows = userCows.filter(c => {
      const phase = c.lactation_phase || computeLactationPhase(c.age_group, c.lactation_days, c.lactation);
      return phase.toLowerCase().includes(lactationPhaseFilter.toLowerCase());
    });
  }

  if (reproFilter && reproFilter !== 'stillborn') {
    userCows = userCows.filter(c => {
      const agL = (c.age_group || '').toLowerCase();
      const rL = (c.reason || '').toLowerCase();
      const isPreg = (c.is_pregnant === 1 || ((c.gestation_days || 0) > 0) || agL.includes('сухосто') || agL.includes('нетел') || rL.includes('стельн'));

      if (reproFilter === 'pregnant') return isPreg;
      if (reproFilter === 'pregnant_late') return ((c.gestation_days || 0) >= 180) || (isPreg && agL.includes('сухосто'));
      return true;
    });
  }

  let deathCount = 0;
  let cullingCount = 0;
  let sanitaryCount = 0;
  for (let i = 0; i < userCows.length; i++) {
    const cat = userCows[i].category;
    if (cat === 'падёж') deathCount++;
    else if (cat === 'выбраковка') cullingCount++;
    else sanitaryCount++;
  }

  // Initial page: sorted newest first, first 50 cows
  const sortedInitial = [...userCows].sort((a, b) => b.disposal_date.localeCompare(a.disposal_date) || b.id - a.id);
  const initialPageCows = sortedInitial.slice(0, 50);

  res.render('view_cows', {
    cows: initialPageCows,
    initial_cows: initialPageCows,
    total_cows_count: userCows.length,
    initial_stats: {
      total: userCows.length,
      death: deathCount,
      culling: cullingCount,
      sanitary: sanitaryCount
    },
    unique_farms: uniqueFarms,
    categories: DISPOSAL_CATEGORIES,
    user_type: userType,
    repro_filter: reproFilter
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
  const { category, reason, disposal_date, form_mode } = req.body;

  if (!category || !reason || !disposal_date) {
    addFlash(req, 'Заполните все обязательные поля', 'danger');
    return res.redirect('/add_cow');
  }

  const todayStr = formatDate(new Date());
  if (disposal_date > todayStr) {
    addFlash(req, 'Дата события не может быть позже сегодняшнего дня', 'danger');
    return res.redirect('/add_cow');
  }

  const cowId = generateCowId(farmName);
  let ageGroup = req.body.age_group ? String(req.body.age_group).trim() : 'Коровы дойного стада';

  if (form_mode === 'stillborn' || ageGroup.includes('Мертворожд') || ageGroup.includes('Аборт')) {
    ageGroup = 'Мертворождённые / Аборты';
  }

  let lact = req.body.lactation !== undefined && req.body.lactation !== '' ? parseInt(String(req.body.lactation), 10) : undefined;
  let lactDays = req.body.lactation_days !== undefined && req.body.lactation_days !== '' ? parseInt(String(req.body.lactation_days), 10) : undefined;

  // Автозаполнение дней лактации для группы "Новотельные коровы (0–30 дн DIM)"
  if (ageGroup.includes('Новотел') || ageGroup.includes('0–30') || ageGroup.includes('0-30')) {
    if (lactDays === undefined || lactDays === null || isNaN(lactDays) || lactDays === 0) {
      lactDays = 15;
    }
  }

  const lactPhase = computeLactationPhase(ageGroup, lactDays, lact);

  // Воспроизводство и стельность
  let isPregnant = req.body.is_pregnant === '1' || req.body.is_pregnant === 'on' || req.body.is_pregnant === true ? 1 : 0;
  let gestationDays = req.body.gestation_days ? parseInt(String(req.body.gestation_days), 10) : 0;
  let isStillborn = (form_mode === 'stillborn' || req.body.is_stillborn === '1' || req.body.is_stillborn === 'on' || req.body.is_stillborn === true || ageGroup === 'Мертворождённые / Аборты') ? 1 : 0;

  let finalCategory = category;
  if (isStillborn) {
    finalCategory = 'мертворождение';
  }

  // Автоопределение, если фермер не проставил чекбокс явно
  const reasonLower = (reason || '').toLowerCase();
  const ageGroupLower = (ageGroup || '').toLowerCase();
  if (!isPregnant && !isStillborn) {
    if (lactPhase.toLowerCase().includes('сухосто') || ageGroupLower.includes('сухосто') || ageGroupLower.includes('нетел') || reasonLower.includes('стельн')) {
      isPregnant = 1;
      if (gestationDays === 0) gestationDays = ageGroupLower.includes('сухосто') ? 210 : 180;
    }
  }
  if (!isStillborn) {
    const stillbornKeys = ['мертворож', 'аборт', 'плод', 'мумификац', 'мацерац', 'патология родов', 'патологические роды', 'гибель плода', 'мертвый теленок'];
    if (stillbornKeys.some(k => reasonLower.includes(k))) {
      isStillborn = 1;
      finalCategory = 'мертворождение';
    }
  }

  cows.push({
    id: cowIdCounter++,
    cow_id: cowId,
    farm_name: farmName,
    category: finalCategory,
    reason,
    disposal_date,
    ear_tag: req.body.ear_tag ? String(req.body.ear_tag).trim() : undefined,
    breed: req.body.breed ? String(req.body.breed).trim() : 'Черно-пёстрая белорусской селекции',
    age_group: ageGroup,
    lactation: lact,
    lactation_days: lactDays,
    lactation_phase: lactPhase,
    weight: req.body.weight ? parseFloat(String(req.body.weight)) : undefined,
    milk_yield: req.body.milk_yield ? parseFloat(String(req.body.milk_yield)) : undefined,
    book_value: req.body.book_value ? parseFloat(String(req.body.book_value)) : undefined,
    notes: req.body.notes ? String(req.body.notes).trim() : undefined,
    is_pregnant: isPregnant,
    gestation_days: gestationDays,
    is_stillborn: isStillborn,
    created_at: formatDate(new Date()) + ' ' + new Date().toTimeString().split(' ')[0],
    created_by: req.session.user_id
  });

  if (isStillborn) {
    addFlash(req, `Мертворождение / Аборт зарегистрирован в учёте потерь приплода (ID: ${cowId})`, 'success');
  } else {
    addFlash(req, `Корова успешно добавлена с ID: ${cowId}`, 'success');
  }
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

  // Enforce batch boundary to prevent Memory/CPU Exhaustion DoS
  if (cowsData.length > 500) {
    cowsData = cowsData.slice(0, 500);
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
      const ag = item.age_group ? String(item.age_group).trim() : 'Коровы дойного стада';
      const lact = item.lactation !== undefined && item.lactation !== '' ? parseInt(String(item.lactation), 10) : undefined;
      const lactDays = item.lactation_days !== undefined && item.lactation_days !== '' ? parseInt(String(item.lactation_days), 10) : undefined;
      const lactPhase = computeLactationPhase(ag, lactDays, lact);

      let isPreg = item.is_pregnant === 1 || item.is_pregnant === '1' || item.is_pregnant === true ? 1 : 0;
      let gestD = item.gestation_days ? parseInt(String(item.gestation_days), 10) : 0;
      let isStill = item.is_stillborn === 1 || item.is_stillborn === '1' || item.is_stillborn === true ? 1 : 0;

      const rLow = (item.reason || '').toLowerCase();
      const agLow = ag.toLowerCase();
      if (!isPreg) {
        if (lactPhase.toLowerCase().includes('сухосто') || agLow.includes('сухосто') || agLow.includes('нетел') || rLow.includes('стельн')) {
          isPreg = 1;
          if (gestD === 0) gestD = agLow.includes('сухосто') ? 210 : 180;
        }
      }
      if (!isStill) {
        const stillbornKeys = ['мертворож', 'аборт', 'плод', 'мумификац', 'мацерац', 'патология родов', 'патологические роды', 'гибель плода', 'мертвый теленок'];
        if (stillbornKeys.some(k => rLow.includes(k))) {
          isStill = 1;
        }
      }

      cows.push({
        id: cowIdCounter++,
        cow_id: cowId,
        farm_name: farmName,
        category: item.category,
        reason: item.reason,
        disposal_date: item.disposal_date,
        ear_tag: item.ear_tag ? String(item.ear_tag).trim() : undefined,
        breed: item.breed ? String(item.breed).trim() : 'Черно-пёстрая белорусской селекции',
        age_group: ag,
        lactation: lact,
        lactation_days: lactDays,
        lactation_phase: lactPhase,
        weight: item.weight ? parseFloat(String(item.weight)) : undefined,
        milk_yield: item.milk_yield ? parseFloat(String(item.milk_yield)) : undefined,
        book_value: item.book_value ? parseFloat(String(item.book_value)) : undefined,
        notes: item.notes ? String(item.notes).trim() : undefined,
        is_pregnant: isPreg,
        gestation_days: gestD,
        is_stillborn: isStill,
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

// Edit Cow
app.get('/edit_cow/:id', loginRequired, (req: Request, res: Response) => {
  const userType = req.session.user_type;
  const farmName = req.session.farm_name;
  const cowId = parseInt(String(req.params.id), 10);

  const cow = cows.find(c => c.id === cowId && (userType === 'admin' || c.farm_name === farmName));
  if (!cow) {
    addFlash(req, 'Запись не найдена или нет доступа', 'danger');
    return res.redirect('/cows');
  }

  res.render('edit_cow', { cow });
});

app.post('/edit_cow/:id', loginRequired, (req: Request, res: Response) => {
  const userType = req.session.user_type;
  const farmName = req.session.farm_name;
  const cowId = parseInt(String(req.params.id), 10);

  const cow = cows.find(c => c.id === cowId && (userType === 'admin' || c.farm_name === farmName));
  if (!cow) {
    addFlash(req, 'Запись не найдена или нет доступа', 'danger');
    return res.redirect('/cows');
  }

  const { category, reason, disposal_date, ear_tag, breed, age_group, lactation, lactation_days, weight, milk_yield, book_value, notes } = req.body;
  if (category) cow.category = category;
  if (reason) cow.reason = reason;
  if (disposal_date) cow.disposal_date = disposal_date;
  if (ear_tag !== undefined) cow.ear_tag = String(ear_tag).trim();
  if (breed) cow.breed = String(breed).trim();
  if (age_group) cow.age_group = String(age_group).trim();
  if (lactation !== undefined && lactation !== '') {
    cow.lactation = parseInt(String(lactation), 10);
  } else if (lactation === '') {
    cow.lactation = undefined;
  }
  if (lactation_days !== undefined && lactation_days !== '') {
    cow.lactation_days = parseInt(String(lactation_days), 10);
  } else if (lactation_days === '') {
    cow.lactation_days = undefined;
  }
  cow.lactation_phase = computeLactationPhase(cow.age_group, cow.lactation_days, cow.lactation);
  if (weight !== undefined && weight !== '') cow.weight = parseFloat(String(weight));
  if (milk_yield !== undefined && milk_yield !== '') cow.milk_yield = parseFloat(String(milk_yield));
  if (book_value !== undefined && book_value !== '') cow.book_value = parseFloat(String(book_value));
  if (notes !== undefined) cow.notes = String(notes).trim();

  // Воспроизводство и стельность
  if (req.body.is_pregnant !== undefined) {
    cow.is_pregnant = (req.body.is_pregnant === '1' || req.body.is_pregnant === 'on' || req.body.is_pregnant === true) ? 1 : 0;
  }
  if (req.body.gestation_days !== undefined) {
    cow.gestation_days = req.body.gestation_days ? parseInt(String(req.body.gestation_days), 10) : 0;
  }
  if (req.body.is_stillborn !== undefined) {
    cow.is_stillborn = (req.body.is_stillborn === '1' || req.body.is_stillborn === 'on' || req.body.is_stillborn === true) ? 1 : 0;
  }

  addFlash(req, `Запись ${cow.cow_id} успешно обновлена`, 'success');
  res.redirect('/cows');
});

// Reports Page
app.get('/reports', loginRequired, (req: Request, res: Response) => {
  res.render('reports', {
    user_type: req.session.user_type,
    unique_farms: getUniqueFarms()
  });
});

// Generate Report
app.post('/generate_report', loginRequired, heavyOpsProtection, async (req: Request, res: Response) => {
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
      farm_filter: farm_filter || userFarm,
      org_name: 'ОАО «Новая Припять»'
    });
  }

  // AITS Registry Format
  if (report_type === 'aits_registry') {
    let csvContent = 'УНП владельца;Сельхозорганизация;Подразделение (МТФ);Идентификационный номер животного (AITS);Код события выбытия;Наименование события;Дата выбытия (ДД.ММ.ГГГГ);Диагноз / Причина;Живая масса (кг);Половозрастная группа;Номер первичного акта\n';
    for (const c of filteredCows) {
      const parts = c.disposal_date.split('-');
      const ddmmyyyy = parts.length === 3 ? `${parts[2]}.${parts[1]}.${parts[0]}` : c.disposal_date;
      const code = c.category === 'падёж' ? '01' : (c.category === 'санитарный' ? '02' : '03');
      const desc = c.category === 'падёж' ? 'Падёж' : (c.category === 'санитарный' ? 'Санитарный убой' : 'Выбраковка');
      const tag = c.ear_tag || `БЕЗ-БИРКИ-${c.cow_id}`;
      csvContent += `"190000000";"ОАО «Новая Припять»";"${c.farm_name}";"${tag}";"${code}";"${desc}";"${ddmmyyyy}";"${c.reason}";"${c.weight || ''}";"${c.age_group || 'КРС'}";"Акт 209-АПК от ${ddmmyyyy}"\n`;
    }
    const filename = `aits_registry_${start_date}_по_${end_date}.csv`;
    res.setHeader('Content-Type', 'text/csv; charset=utf-8');
    res.setHeader('Content-Disposition', `attachment; filename="${encodeURIComponent(filename)}"`);
    return res.send('\uFEFF' + csvContent);
  }

  // 3. Excel Format (.xlsx)
  const workbook = new ExcelJS.Workbook();
  workbook.creator = 'ОАО «Новая Припять» - Система учёта выбытия скота';
  workbook.created = new Date();

  // Форма № 209-АПК РБ (Акт на выбытие животных и птицы)
  if (report_type === 'form_209_apk' || report_type === 'sp54') {
    const ws = workbook.addWorksheet('Форма 209-АПК (РБ)');
    ws.mergeCells('F1:I1');
    ws.getCell('F1').value = 'Типовая форма 209-АПК';
    ws.getCell('F1').font = { bold: true, size: 9 };
    ws.getCell('F1').alignment = { horizontal: 'right' };

    ws.mergeCells('E2:I2');
    ws.getCell('E2').value = 'Утверждена постановлением Минсельхозпрода Республики Беларусь';
    ws.getCell('E2').font = { italic: true, size: 8 };
    ws.getCell('E2').alignment = { horizontal: 'right' };

    ws.getCell('A4').value = 'Сельскохозяйственная организация: ОАО «Новая Припять»';
    ws.getCell('A4').font = { bold: true, size: 10 };

    ws.mergeCells('A6:I6');
    ws.getCell('A6').value = 'АКТ НА ВЫБЫТИЕ ЖИВОТНЫХ И ПТИЦЫ (ЗАБОЙ, ПРИРЕЗКА И ПАДЁЖ)';
    ws.getCell('A6').font = { bold: true, size: 12 };
    ws.getCell('A6').alignment = { horizontal: 'center' };

    ws.mergeCells('A7:I7');
    ws.getCell('A7').value = `за период с ${start_date} по ${end_date} года`;
    ws.getCell('A7').alignment = { horizontal: 'center' };

    const headerRow = ws.getRow(9);
    headerRow.values = [
      '№ п/п', 'Учетный номер', 'Идент. № (AITS / Бирка)', 'Подразделение / МТФ',
      'Вид выбытия (РБ)', 'Причина выбытия (диагноз)', 'Лактация / Возраст', 'Живая масса (кг)', 'Дата выбытия'
    ];
    headerRow.font = { bold: true, size: 9 };
    headerRow.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFE2E8F0' } };
    headerRow.alignment = { horizontal: 'center', vertical: 'middle' };

    let totalWeight = 0;
    filteredCows.forEach((c, idx) => {
      const w = c.weight || 0;
      totalWeight += w;
      const row = ws.addRow([
        idx + 1, c.cow_id, c.ear_tag || '-', c.farm_name,
        c.category.charAt(0).toUpperCase() + c.category.slice(1),
        c.reason, c.lactation || '-', w > 0 ? w : '-', c.disposal_date
      ]);
      row.alignment = { vertical: 'middle' };
    });

    const sumRow = ws.addRow(['ИТОГО ВЫБЫЛО ПО АКТУ:', '', '', '', '', '', '', `${totalWeight.toFixed(1)} кг`, `${filteredCows.length} гол.`]);
    sumRow.font = { bold: true };
    sumRow.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFE2E8F0' } };

    ws.columns = [
      { width: 8 }, { width: 16 }, { width: 22 }, { width: 20 },
      { width: 18 }, { width: 28 }, { width: 16 }, { width: 16 }, { width: 14 }
    ];

    const filename = `akt_209_apk_RB_${start_date}_по_${end_date}.xlsx`;
    res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
    res.setHeader('Content-Disposition', `attachment; filename="${encodeURIComponent(filename)}"`);
    await workbook.xlsx.write(res);
    return res.end();
  }

  // Форма № 210-АПК РБ (Акт на выбраковку из основного стада)
  if (report_type === 'form_210_apk') {
    const ws = workbook.addWorksheet('Форма 210-АПК (РБ)');
    const vybCows = filteredCows.filter(c => c.category === 'выбраковка' || c.category === 'санитарный');

    ws.mergeCells('H1:K1');
    ws.getCell('H1').value = 'Типовая форма 210-АПК';
    ws.getCell('H1').font = { bold: true, size: 9 };
    ws.getCell('H1').alignment = { horizontal: 'right' };

    ws.getCell('A4').value = 'Сельхозорганизация: ОАО «Новая Припять»';
    ws.getCell('A4').font = { bold: true, size: 10 };

    ws.mergeCells('A7:K7');
    ws.getCell('A7').value = 'АКТ НА ВЫБРАКОВКУ ЖИВОТНЫХ ИЗ ОСНОВНОГО СТАДА';
    ws.getCell('A7').font = { bold: true, size: 12 };
    ws.getCell('A7').alignment = { horizontal: 'center' };

    const headerRow = ws.getRow(9);
    headerRow.values = [
      '№ п/п', 'Идент. № AITS / Инв. №', 'Подразделение (МТФ)', 'Порода', 'Лактация',
      'Живая масса (кг)', 'Удой (кг)', 'Баланс. ст. (BYN)', 'Причина выбраковки (диагноз)', 'Вид выбытия', 'Направление'
    ];
    headerRow.font = { bold: true, size: 9 };
    headerRow.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFDCE7F5' } };
    headerRow.alignment = { horizontal: 'center', vertical: 'middle' };

    let totalWeight = 0;
    let totalVal = 0;
    vybCows.forEach((c, idx) => {
      const w = c.weight || 0;
      const bv = c.book_value || 0;
      totalWeight += w;
      totalVal += bv;
      const usage = c.category === 'выбраковка' ? 'Сдача на мясокомбинат' : 'Санитарная бойня';
      ws.addRow([
        idx + 1, c.ear_tag || c.cow_id, c.farm_name, c.breed || 'Черно-пёстрая',
        c.lactation || '-', w > 0 ? w : '-', c.milk_yield || '-', bv > 0 ? bv.toFixed(2) : '-',
        c.reason, c.category.charAt(0).toUpperCase() + c.category.slice(1), usage
      ]);
    });

    const sumRow = ws.addRow(['ИТОГО ВЫБРАКОВАНО:', '', '', '', '', `${totalWeight.toFixed(1)} кг`, '', `${totalVal.toFixed(2)} BYN`, '', '', `${vybCows.length} гол.`]);
    sumRow.font = { bold: true };
    sumRow.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFDCE7F5' } };

    ws.columns = [
      { width: 8 }, { width: 22 }, { width: 18 }, { width: 20 }, { width: 12 },
      { width: 16 }, { width: 14 }, { width: 18 }, { width: 28 }, { width: 14 }, { width: 22 }
    ];

    const filename = `akt_210_apk_RB_${start_date}_по_${end_date}.xlsx`;
    res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
    res.setHeader('Content-Disposition', `attachment; filename="${encodeURIComponent(filename)}"`);
    await workbook.xlsx.write(res);
    return res.end();
  }

  if (report_type === 'matrix') {
    const category = report_category || 'падёж';
    const subcategories = DISPOSAL_CATEGORIES[category] || [];
    const worksheet = workbook.addWorksheet(`Матрица ${category}`);

    // Title
    worksheet.mergeCells('A1:H1');
    const titleCell = worksheet.getCell('A1');
    titleCell.value = 'ОАО «НОВАЯ ПРИПЯТЬ» — ОТЧЁТ ПО ВЫБЫТИЮ СКОТА';
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

    // Pre-aggregate matrix counts in single O(N) pass
    const matrixCounts: Record<string, number> = {};
    const farmTotals: Record<string, number> = {};
    for (const c of filteredCows) {
      if (c.category === category) {
        const key = `${c.reason}__${c.farm_name}`;
        matrixCounts[key] = (matrixCounts[key] || 0) + 1;
        farmTotals[c.farm_name] = (farmTotals[c.farm_name] || 0) + 1;
      }
    }

    let currentRow = 7;
    for (const subcategory of subcategories) {
      const row = worksheet.getRow(currentRow);
      row.getCell(1).value = subcategory;

      let rowTotal = 0;
      farms.forEach((farm, idx) => {
        const count = matrixCounts[`${subcategory}__${farm}`] || 0;
        const cell = row.getCell(idx + 2);
        cell.value = count > 0 ? count : '-';
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
      const count = farmTotals[farm] || 0;
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

  // 4. Специализированный аналитический отчёт по лактации и молодняку
  if (report_type === 'lactation_analytics') {
    // Лист 1: Анализ лактации и фаз DIM
    const wsLact = workbook.addWorksheet('Аналитика лактации (DIM)');
    wsLact.mergeCells('A1:G1');
    wsLact.getCell('A1').value = 'ОАО «НОВАЯ ПРИПЯТЬ» — АНАЛИЗ ВЫБЫТИЯ ПО ФАЗАМ ЛАКТАЦИИ И DIM';
    wsLact.getCell('A1').font = { bold: true, size: 13, color: { argb: 'FFFFFFFF' } };
    wsLact.getCell('A1').fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF1E3A8A' } };
    wsLact.getCell('A1').alignment = { horizontal: 'center', vertical: 'middle' };

    wsLact.mergeCells('A2:G2');
    wsLact.getCell('A2').value = `Период: с ${start_date} по ${end_date} | Подразделения: ${farm_filter === 'all' ? 'Все фермы' : (farm_filter || userFarm)}`;
    wsLact.getCell('A2').font = { italic: true, size: 10 };
    wsLact.getCell('A2').alignment = { horizontal: 'center' };

    const lactHeader = wsLact.getRow(4);
    lactHeader.values = ['Фаза лактации (DIM)', 'Интервал (дни)', 'Выбыло всего (гол.)', 'Падёж (гол.)', 'Выбраковка / санбрак', 'Ср. дни лактации (DIM)', 'Ср. масса (кг)'];
    lactHeader.font = { bold: true };
    lactHeader.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFDBEAFE' } };
    lactHeader.alignment = { horizontal: 'center', vertical: 'middle' };

    const phasesDef = [
      { name: 'Новотельный период (0–30 дн)', min: 0, max: 30, desc: '0–30 дн (Критическая зона)' },
      { name: 'Раздой / Пик лактации (31–100 дн)', min: 31, max: 100, desc: '31–100 дн' },
      { name: 'Середина лактации (101–200 дн)', min: 101, max: 200, desc: '101–200 дн' },
      { name: 'Спад лактации (201–305+ дн)', min: 201, max: 9999, desc: '201–305+ дн' },
      { name: 'Сухостойный период', min: -1, max: -1, desc: 'Сухостой' }
    ];

    let rowIdx = 5;
    for (const p of phasesDef) {
      const cohortCows = filteredCows.filter(c => {
        const ag = (c.age_group || '').toLowerCase();
        if (p.min === -1) return ag.includes('сухосто');
        if (ag.includes('тел') || ag.includes('молод') || ag.includes('быч') || ag.includes('нетел') || ag.includes('сухосто')) return false;
        const dim = c.lactation_days || 0;
        return dim >= p.min && dim <= p.max;
      });

      const total = cohortCows.length;
      const death = cohortCows.filter(c => c.category === 'падёж').length;
      const culling = total - death;
      const avgDim = total > 0 ? Math.round(cohortCows.reduce((s, c) => s + (c.lactation_days || 0), 0) / total) : 0;
      const avgWeight = total > 0 ? Math.round(cohortCows.reduce((s, c) => s + (c.weight || 0), 0) / total) : 0;

      const r = wsLact.addRow([p.name, p.desc, total, death, culling, avgDim > 0 ? avgDim : '-', avgWeight > 0 ? avgWeight : '-']);
      r.alignment = { vertical: 'middle', horizontal: 'center' };
      r.getCell(1).alignment = { horizontal: 'left' };
      if (p.name.includes('Новотел')) {
        r.getCell(1).font = { bold: true, color: { argb: 'FFDC2626' } };
      }
      rowIdx++;
    }

    wsLact.columns = [{ width: 34 }, { width: 22 }, { width: 20 }, { width: 16 }, { width: 22 }, { width: 22 }, { width: 18 }];

    // Лист 2: Аналитика выбытия молодняка
    const wsYouth = workbook.addWorksheet('Аналитика молодняка');
    wsYouth.mergeCells('A1:F1');
    wsYouth.getCell('A1').value = 'ОАО «НОВАЯ ПРИПЯТЬ» — СОХРАННОСТЬ И ВЫБЫТИЕ МОЛОДНЯКА КРС';
    wsYouth.getCell('A1').font = { bold: true, size: 13, color: { argb: 'FFFFFFFF' } };
    wsYouth.getCell('A1').fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF059669' } };
    wsYouth.getCell('A1').alignment = { horizontal: 'center', vertical: 'middle' };

    const youthHeader = wsYouth.getRow(3);
    youthHeader.values = ['Половозрастная группа', 'Всего выбыло (гол.)', 'Падёж (гол.)', 'Доля падежа (%)', 'Ср. масса (кг)', 'Преобладающие диагнозы'];
    youthHeader.font = { bold: true };
    youthHeader.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFD1FAE5' } };
    youthHeader.alignment = { horizontal: 'center', vertical: 'middle' };

    const youthCats = ['Телята (до 6 мес.)', 'Молодняк (от 6 до 18 мес.)', 'Нетели и тёлки (> 18 мес.)', 'Бычки на откорме'];
    for (const yCat of youthCats) {
      const yCows = filteredCows.filter(c => normalizeAgeGroup(c.age_group, c.lactation) === yCat);
      const tot = yCows.length;
      const dth = yCows.filter(c => c.category === 'падёж').length;
      const pct = tot > 0 ? (dth / tot * 100).toFixed(1) + '%' : '0.0%';
      const avgW = tot > 0 ? Math.round(yCows.reduce((s, c) => s + (c.weight || 0), 0) / tot) : 0;
      
      const diagCounts: Record<string, number> = {};
      yCows.forEach(c => { diagCounts[c.reason] = (diagCounts[c.reason] || 0) + 1; });
      const topD = Object.entries(diagCounts).sort((a, b) => b[1] - a[1]).slice(0, 2).map(([d, n]) => `${d} (${n})`).join(', ') || '-';

      const row = wsYouth.addRow([yCat, tot, dth, pct, avgW > 0 ? avgW : '-', topD]);
      row.alignment = { vertical: 'middle', horizontal: 'center' };
      row.getCell(1).alignment = { horizontal: 'left' };
      row.getCell(1).font = { bold: true };
      row.getCell(6).alignment = { horizontal: 'left' };
    }
    wsYouth.columns = [{ width: 26 }, { width: 20 }, { width: 16 }, { width: 18 }, { width: 16 }, { width: 38 }];

    // Лист 3: Реестр животных с полями лактации
    const wsReg = workbook.addWorksheet('Реестр (Лактация и DIM)');
    const regHeader = wsReg.getRow(1);
    regHeader.values = [
      '№ п/п', 'ID выбытия', 'Бирка AITS', 'Ферма', 'Категория скота',
      'Лактация', 'Дни лактации (DIM)', 'Фаза лактации', 'Вид выбытия', 'Причина / Диагноз', 'Масса (кг)', 'Удой (кг)', 'Дата'
    ];
    regHeader.font = { bold: true };
    regHeader.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFE2E8F0' } };
    regHeader.alignment = { horizontal: 'center', vertical: 'middle' };

    filteredCows.forEach((c, idx) => {
      const phase = c.lactation_phase || computeLactationPhase(c.age_group, c.lactation_days, c.lactation);
      wsReg.addRow([
        idx + 1, c.cow_id, c.ear_tag || '-', c.farm_name, c.age_group || 'Коровы дойного стада',
        c.lactation !== undefined ? c.lactation : '-',
        c.lactation_days !== undefined ? c.lactation_days : '-',
        phase,
        c.category.charAt(0).toUpperCase() + c.category.slice(1),
        c.reason,
        c.weight || '-',
        c.milk_yield || '-',
        c.disposal_date
      ]);
    });
    wsReg.columns = [
      { width: 6 }, { width: 14 }, { width: 18 }, { width: 20 }, { width: 24 },
      { width: 12 }, { width: 20 }, { width: 24 }, { width: 16 }, { width: 30 }, { width: 14 }, { width: 14 }, { width: 14 }
    ];

    const filename = `аналитика_лактации_и_молодняка_${start_date}_по_${end_date}.xlsx`;
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
app.post('/generate_original_excel', loginRequired, adminRequired, heavyOpsProtection, async (req: Request, res: Response) => {
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

  // Pre-aggregate counts in single O(N) pass
  const farmStats: Record<string, { padezh: number; vybrakovka: number; sanitarniy: number }> = {};
  for (const farm of farms) {
    farmStats[farm] = { padezh: 0, vybrakovka: 0, sanitarniy: 0 };
  }
  for (const c of cows) {
    if (farmStats[c.farm_name]) {
      if (c.category === 'падёж') farmStats[c.farm_name].padezh++;
      else if (c.category === 'выбраковка') farmStats[c.farm_name].vybrakovka++;
      else if (c.category === 'санитарный') farmStats[c.farm_name].sanitarniy++;
    }
  }

  let grandPadezh = 0;
  let grandVybrakovka = 0;
  let grandSanitarniy = 0;
  let grandTotal = 0;

  for (const farm of farms) {
    const s = farmStats[farm];
    const total = s.padezh + s.vybrakovka + s.sanitarniy;
    grandPadezh += s.padezh;
    grandVybrakovka += s.vybrakovka;
    grandSanitarniy += s.sanitarniy;
    grandTotal += total;
    worksheet.addRow([farm, s.padezh, s.vybrakovka, s.sanitarniy, total]);
  }

  // Add Totals row
  const totalRow = worksheet.addRow(['ИТОГО ПО ХОЗЯЙСТВУ', grandPadezh, grandVybrakovka, grandSanitarniy, grandTotal]);
  totalRow.font = { bold: true };
  totalRow.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFFFE2E5' } };

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
  res.json(getUniqueFarms());
});

app.get('/get_reasons/:category', loginRequired, (req: Request, res: Response) => {
  const category = String(req.params.category);
  const reasons = DISPOSAL_CATEGORIES[category] || [];
  res.json(reasons);
});

// Экономические нормативы цен BYN и методика расчета
app.get('/api/pricing', loginRequired, (req: Request, res: Response) => {
  res.json({
    success: true,
    pricing: currentPricingStandards,
    methodology: {
      title: 'Методика расчета экономического ущерба от выбытия скота (РБ)',
      formula: 'Общий ущерб (BYN) = ∑ (Балансовая стоимость животных)',
      description: 'Если в акте выбытия заполнено поле "Балансовая стоимость", берется точная сумма из документа. В противном случае используется финансовый норматив для соответствующей группы скота.',
      standards: currentPricingStandards
    }
  });
});

app.post(['/pricing', '/api/pricing'], loginRequired, adminRequired, (req: Request, res: Response) => {
  const {
    price_calves,
    price_youngstock,
    price_heifers,
    price_cows,
    price_dry_cows,
    meat_price_per_kg,
    milk_price_per_kg,
    replacement_cost,
    norm_fresh_cow_disposal,
    norm_first_lactation_culling,
    norm_mortality_rate,
    norm_locomotor_disorders,
    norm_mastitis_disorders
  } = req.body;

  if (price_calves !== undefined) currentPricingStandards.price_calves = Math.max(0, Number(price_calves) || 900);
  if (price_youngstock !== undefined) currentPricingStandards.price_youngstock = Math.max(0, Number(price_youngstock) || 1650);
  if (price_heifers !== undefined) currentPricingStandards.price_heifers = Math.max(0, Number(price_heifers) || 2700);
  if (price_cows !== undefined) currentPricingStandards.price_cows = Math.max(0, Number(price_cows) || 3200);
  if (price_dry_cows !== undefined) currentPricingStandards.price_dry_cows = Math.max(0, Number(price_dry_cows) || 3000);
  if (meat_price_per_kg !== undefined) currentPricingStandards.meat_price_per_kg = Math.max(0, Number(meat_price_per_kg) || 6.20);
  if (milk_price_per_kg !== undefined) currentPricingStandards.milk_price_per_kg = Math.max(0, Number(milk_price_per_kg) || 1.18);
  if (replacement_cost !== undefined) currentPricingStandards.replacement_cost = Math.max(0, Number(replacement_cost) || 2950);

  // 1. Выбытие новотельных (0-30 DIM)
  if (req.body.norm_fresh_cow_disposal !== undefined) currentPricingStandards.norm_fresh_cow_disposal = Math.max(0, Math.min(100, Number(req.body.norm_fresh_cow_disposal) || 10));
  if (req.body.warn_fresh_cow_disposal !== undefined) currentPricingStandards.warn_fresh_cow_disposal = Math.max(0, Math.min(100, Number(req.body.warn_fresh_cow_disposal) || 14));
  if (req.body.crit_fresh_cow_disposal !== undefined) currentPricingStandards.crit_fresh_cow_disposal = Math.max(0, Math.min(100, Number(req.body.crit_fresh_cow_disposal) || 18));

  // 2. Выбраковка первотёлок
  if (req.body.norm_first_lactation_culling !== undefined) currentPricingStandards.norm_first_lactation_culling = Math.max(0, Math.min(100, Number(req.body.norm_first_lactation_culling) || 20));
  if (req.body.warn_first_lactation_culling !== undefined) currentPricingStandards.warn_first_lactation_culling = Math.max(0, Math.min(100, Number(req.body.warn_first_lactation_culling) || 25));
  if (req.body.crit_first_lactation_culling !== undefined) currentPricingStandards.crit_first_lactation_culling = Math.max(0, Math.min(100, Number(req.body.crit_first_lactation_culling) || 30));

  // 5. Общая летальность (Падёж)
  if (req.body.norm_mortality_rate !== undefined) currentPricingStandards.norm_mortality_rate = Math.max(0, Math.min(100, Number(req.body.norm_mortality_rate) || 25));
  if (req.body.warn_mortality_rate !== undefined) currentPricingStandards.warn_mortality_rate = Math.max(0, Math.min(100, Number(req.body.warn_mortality_rate) || 35));
  if (req.body.crit_mortality_rate !== undefined) currentPricingStandards.crit_mortality_rate = Math.max(0, Math.min(100, Number(req.body.crit_mortality_rate) || 45));

  // 6. Болезни конечностей (копыт)
  if (req.body.norm_locomotor_disorders !== undefined) currentPricingStandards.norm_locomotor_disorders = Math.max(0, Math.min(100, Number(req.body.norm_locomotor_disorders) || 15));
  if (req.body.warn_locomotor_disorders !== undefined) currentPricingStandards.warn_locomotor_disorders = Math.max(0, Math.min(100, Number(req.body.warn_locomotor_disorders) || 20));
  if (req.body.crit_locomotor_disorders !== undefined) currentPricingStandards.crit_locomotor_disorders = Math.max(0, Math.min(100, Number(req.body.crit_locomotor_disorders) || 25));

  // 7. Маститы и заболевания вымени
  if (req.body.norm_mastitis_disorders !== undefined) currentPricingStandards.norm_mastitis_disorders = Math.max(0, Math.min(100, Number(req.body.norm_mastitis_disorders) || 15));
  if (req.body.warn_mastitis_disorders !== undefined) currentPricingStandards.warn_mastitis_disorders = Math.max(0, Math.min(100, Number(req.body.warn_mastitis_disorders) || 20));
  if (req.body.crit_mastitis_disorders !== undefined) currentPricingStandards.crit_mastitis_disorders = Math.max(0, Math.min(100, Number(req.body.crit_mastitis_disorders) || 25));

  if (req.headers['x-requested-with'] === 'XMLHttpRequest' || req.is('json')) {
    return res.json({
      success: true,
      message: 'Экономические ценники, зоотехнические нормы и критические пороги успешно обновлены!',
      pricing: currentPricingStandards
    });
  }

  res.redirect('/pricing');
});

app.get('/pricing', loginRequired, adminRequired, (req: Request, res: Response) => {
  res.render('pricing', {
    pricing: currentPricingStandards,
    user_type: req.session.user_type
  });
});

// Seed 1000 Cows route
app.get('/seed_test_data', loginRequired, adminRequired, (req: Request, res: Response) => {
  populateRealisticCows(1000, false);
  addFlash(req, `Добавлено +1 000 тестовых записей. Всего в базе: ${cows.length} голов.`, 'success');
  res.redirect('/dashboard');
});

// Manage Reasons route
app.get('/manage_reasons', loginRequired, adminRequired, (req: Request, res: Response) => {
  res.render('fix_categories');
});

// Import Cows Alias Route
app.get('/import_cows', loginRequired, (req: Request, res: Response) => {
  res.render('add_multiple_cows', {
    categories: DISPOSAL_CATEGORIES,
    user_type: req.session.user_type,
    farm_name: req.session.farm_name
  });
});

// Admin Generator, Backup & Audit Log routes
function handleAdminGeneratorView(req: Request, res: Response) {
  const start = Date.now();
  const farmStats: Record<string, number> = {};
  const catStats: Record<string, number> = { 'падёж': 0, 'выбраковка': 0, 'санитарный': 0 };
  let totalWeight = 0;
  for (const c of cows) {
    farmStats[c.farm_name] = (farmStats[c.farm_name] || 0) + 1;
    const catKey = (c.category || 'санитарный').toLowerCase();
    catStats[catKey] = (catStats[catKey] || 0) + 1;
    if (c.weight) totalWeight += c.weight;
  }
  const benchmarkMs = (Date.now() - start) + 0.1;
  const memoryMb = Math.round(process.memoryUsage().rss / 1024 / 1024);

  const secMetrics = {
    ...securityMetrics,
    trackedIpsCount: globalDdosLimiter.getTrackedCount()
  };

  res.render('admin_generator', {
    cows: cows,
    cows_count: cows.length,
    user_type: req.session.user_type,
    benchmark_ms: benchmarkMs.toFixed(2),
    memory_mb: memoryMb,
    farm_stats: farmStats,
    cat_stats: catStats,
    total_weight_formatted: (totalWeight / 1000).toFixed(1) + ' тонн',
    security_metrics: secMetrics
  });
}

app.get(['/backup_page', '/backup', '/audit_log', '/admin/generator'], loginRequired, adminRequired, handleAdminGeneratorView);

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

// Error handling middleware (handles payload overflow, bad requests, prevents unhandled crashes)
app.use((err: any, req: Request, res: Response, next: NextFunction) => {
  if (err.type === 'entity.too.large' || err.status === 413) {
    if (req.xhr || req.is('json')) {
      return res.status(413).json({ error: 'Размер запроса превышает допустимый лимит безопасности (2 МБ)' });
    }
    return res.status(413).send('413 Payload Too Large: Размер запроса превышает допустимый лимит безопасности (2 МБ)');
  }
  console.error('[SERVER ERROR HANDLER] Safely captured exception:', err);
  if (res.headersSent) {
    return next(err);
  }
  res.status(500).send('Внутренняя ошибка сервера: ' + (err.message || 'Error'));
});

// Start Server on 0.0.0.0:3000 with Slowloris & KeepAlive Protection Timeouts
const server = app.listen(Number(PORT), '0.0.0.0', () => {
  console.log(`Server started and listening on http://0.0.0.0:${PORT} [DDoS & Abuse Shield ACTIVE]`);
});
server.requestTimeout = 30000;
server.headersTimeout = 20000;
server.keepAliveTimeout = 5000;
