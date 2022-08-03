import requests
import os
import json
from progress.bar import IncrementalBar
from datetime import datetime
from pprint import pprint
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive


class Settings:
    def __get_api(app):
        api = 'api не найден в settings.ini'
        with open('settings.ini', encoding='UTF-8') as f:
            for line in f.readlines():
                if app in line:
                    api = line.split()[1].strip()
        return api

    vk_api = __get_api('vk')
    yadisk_api = __get_api('yadisk')


class Tools:
    def unix_time_to_utc(self, unix_time):
        return datetime.utcfromtimestamp(unix_time).strftime('%d-%m-%Y')

    def request(self, type, url, headers='', params=''):
        try:
            res = False
            if type == 'post': 
                res = requests.post(url, headers=headers, params=params)
            if type == 'get': 
                res = requests.get(url, headers=headers, params=params)
            if type == 'put': 
                res = requests.put(url, headers=headers, params=params)
            return res.json()
        except:
            return f'error: {res}'

    def save_api(self, app, api):
        if app == 'vk':
            Settings.vk_api = api

        elif app == 'yadisk':
            Settings.yadisk_api = api

        with open('settings.ini', 'w', encoding='UTF-8') as f:
            f.write(f'yadisk {Settings.yadisk_api}\n')
            f.write(f'vk {Settings.vk_api}\n')


class GoogleDriveOAuth():
    def __init__(self):
        # Название файла json должно быть client_secrets.json
        self.gauth = GoogleAuth()
        self.gauth.LocalWebserverAuth()

    def upload_folder(self, folder):         
        folder_list = os.listdir(folder)
        bar = IncrementalBar('Загрузка фотографий на гугл диск', 
                            max = len(folder_list))
        drive = GoogleDrive(self.gauth)     

        for file_name in folder_list:
            bar.next()
            my_file = drive.CreateFile({'title': f'{file_name}'})
            my_file.SetContentFile(os.path.join(folder, file_name))
            my_file.Upload()
        
        bar.finish()


class YaDisk(Tools):
    def __init__(self):
        self.token = Settings.yadisk_api
        self.url = 'https://cloud-api.yandex.net/v1/disk/'
    
    def __get_header(self):
        return {'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Authorization': f'OAuth {self.token}'}

    def __make_folder(self, folder):
        url = self.url + 'resources'
        headers = self.__get_header()
        params = {'path': folder}
        return self.request('put', url, headers, params)

    def __get_link_to_upload(self, path):
        url = self.url + 'resources/upload'
        headers = self.__get_header()
        params = {'path': path, 'overwrite': 'true'}
        return self.request('get', url, headers, params)

    def upload_folder(self, folder):
        """Метод загружает папку с файлами на яндекс диск"""
        self.__make_folder(folder)

        folder_list = os.listdir(folder)
        bar = IncrementalBar('Загрузка фотографий на яндекс диск', 
                            max = len(folder_list))

        for filename in folder_list:
            bar.next()
            url = self.__get_link_to_upload(f'{folder}/{filename}')
            full_path = os.path.join(folder, filename)
            res = requests.put(url['href'], files={'file':open(full_path, 'rb')})
            if 'error' in res: return pprint(res)
            
        bar.finish()


class VK(Tools):
    def __init__(self, owner_id):
        self.url = 'https://api.vk.com/method/'
        self.token = Settings.vk_api
        self.main_params = {'access_token': self.token, 'v': '5.131'}
        self.owner_id = str(owner_id)

    def __get_max_size_photo(self, photo_sizes):
        sizes = ['w', 'z', 'y', 'r', 'q', 'p', 'o', 'x', 'm', 's']
        for size in sizes:
            for photo_size in photo_sizes:
                if size == photo_size['type']:
                    return photo_size

    def __get_photos_info(self, count, album):
        full_url = self.url + 'photos.get'
        params = {'owner_id': self.owner_id,
                    'count': str(count),
                    'album_id': album,
                    'extended': '1',
                    'photo_sizes': '1',
                    'rev': '1'}
        return self.request('get', full_url, params={**self.main_params, **params})

    def get_albums_list(self):
        full_url = self.url + 'photos.getAlbums'
        params = {'owner_id': self.owner_id}
        res = self.request('get', full_url, params={**self.main_params, **params})
        list_albums = [[id['id'], id['title']] for id in res['response']['items']]
        return list_albums

    def save_photos(self, folder, count=5, album='profile'):
        """Метод скачивает фотографии пользователя vk
        и создает json файл с информацией о фотографиях
        """
        profile_info = self.__get_photos_info(count, album)
        if 'error' in profile_info: return pprint(profile_info)

        bar = IncrementalBar('Скачивание фотографий из вконтакте', 
                                max=len(profile_info['response']['items']))

        for item in profile_info['response']['items']:
            bar.next()
            photo_filename = f'likes {item["likes"]["count"]}.jpg'
            path = os.path.join(os.getcwd(), folder)

            if not os.path.exists(path): os.makedirs(path)
            if os.path.exists(os.path.join(path, photo_filename)): 
                photo_filename = (f'date {self.unix_time_to_utc(item["date"])}'
                                    f' {photo_filename}')
            full_path_photo = os.path.join(path, photo_filename)
            full_path_json = os.path.join(path, 'photos.json')

            with open(full_path_photo, 'wb') as f:
                photo_url = self.__get_max_size_photo(item["sizes"])['url']
                f.write(requests.get(photo_url).content)
            
            json_photos = []
            if os.path.exists(full_path_json): 
                json_photos = json.load(open(full_path_json))
            with open(full_path_json, 'w', encoding='UTF-8') as f:
                json_photos.append({
                    'file_name': photo_filename, 
                    'size': self.__get_max_size_photo(item["sizes"])['type']})
                json.dump(json_photos, f, ensure_ascii=False, indent=2)

        bar.finish()

if __name__ == '__main__':
    yadisk = YaDisk()

    print('Здравствуйте, я помошник бэкапов фотографий с вконтакте')
    vk_id = input('Введите Ваш айди вконтакте\n').strip()
    vk = VK(vk_id)

    while True:
        command = input('a - быстрый бэкап фотографий с профиля на яндекс диск\n'
                        'b - настраиваемый бэкап фотографий\n'
                        'c - настройки api\n'
                        'q - выход\n').lower().strip()
        
        if command == 'a':
            vk.save_photos('vk photos') 
            yadisk.upload_folder('vk photos')
            print('Копирование завершено. Название папки "vk photos"')
            continue
            
        if command == 'b':
            albums = vk.get_albums_list()
            service_albums = [['wall', 'фото со стены'], 
                            ['profile', 'фото профиля'],
                            ['saved', 'сохраненные фото']]
            albums.extend(service_albums)
            for id, album in enumerate(albums):
                print(f'{id}: {album[1]}')

            album_id = albums[int(input('Укажите номер альбома\n'))][0]

            count = input('Введите количество сохраняемых фотографий\n').strip()            
            folder = input('Введите название папки, '
                            'в которую будут сохранены фотографии\n').strip()

            backup_service = input('Введите, на какой диск загружать\n'
                                    'y - yandex disk, g - google drive\n').strip()
            vk.save_photos(folder, count, album_id)

            if backup_service == 'y':            
                yadisk.upload_folder(folder)
            elif backup_service == 'g':
                google = GoogleDriveOAuth()
                google.upload_folder(folder)
            else: 
                print('ошибка команды')
                continue

            print('Копирование завершено.')
            continue

        elif command == 'c':
            command_c = input('Все настройки сохраняются в файле settings.ini\n'
                                'a - настройка api вконтакте\n'
                                'b - настройка api яндекс диска\n'
                                'c - настройка google drive\n'
                                'z - назад в меню\n').lower().strip()

            if command_c == 'z': continue

            elif command_c == 'a':
                command_ca = input('Введите api токен вконтакте\n').strip()
                vk.save_api('vk', command_ca)
                vk = VK(vk_id)
                print('токен изменен')
                continue

            elif command_c == 'b':
                command_cb = input('Введите api токен яндекс диска\n').strip()
                yadisk.save_api('yadisk', command_cb)
                yadisk = YaDisk()
                print('токен изменен')
                continue

            elif command_c == 'c':
                print('Google api с google drive не работает, только OAuth\n'
                        'Для получения json файла OAuth нужно создать приложение\n'
                        'https://console.cloud.google.com/apis/credentials\n'
                        'и переименовать в client_secrets.json\n')
                continue

            else:
                print('Ошибка команды')
                continue

        elif command == 'q':
            print('До свидания!')
            break

        else:
            print('Ошибка команды')
            continue
