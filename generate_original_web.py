# generate_original_web.py
from fill_original_excel import generate_official_template_excel

if __name__ == '__main__':
    wb = generate_official_template_excel()
    wb.save('сводка_выбытия_скота.xlsx')
    print('Сгенерирован файл сводка_выбытия_скота.xlsx')
