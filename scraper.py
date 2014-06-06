#! /usr/bin/env python

import re

from random import choice

from BeautifulSoup import BeautifulSoup
import requests


BASE_URI = 'http://www.parliament.gh'


UA_OPTIONS = [
    ('Mozilla/5.0 (Windows; U; Windows NT 5.1; it; rv:1.8.1.11) '
     'Gecko/20071127 Firefox/2.0.0.11'),
    'Opera/9.25 (Windows NT 5.1; U; en)',
    ('Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1; '
     '.NET CLR 1.1.4322; .NET CLR 2.0.50727)'),
    ('Mozilla/5.0 (compatible; Konqueror/3.5; Linux) KHTML/3.5.5 '
     '(like Gecko) (Kubuntu)'),
    ('Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.8.0.12) Gecko/20070731 '
     'Ubuntu/dapper-security Firefox/1.5.0.12'),
    'Lynx/2.8.5rel.1 libwww-FM/2.14 SSL-MM/1.4.1 GNUTLS/1.2.9'
]


def main(args=None):
    client = MP()
    links, next = client.links(client.start_url)

    print client.details(links[0])


class Scraper(object):
    headers = {'User-Agent': choice(UA_OPTIONS)}    
    
    def get(self, url):
        url = self.resolve(url)    
        return self.bs(requests.get(url, headers=self.headers).content)
    
    def bs(self, content):
        return BeautifulSoup(self.strip(content))
    
    def l(self, s, text):
        try:
            return s.find('a', text=text).parent['href']
        except:
            return None

    def resolve(self, uri):
        if uri is not None:
            if not uri.startswith('http://'):
                if uri.startswith('/'):
                    uri = '%s%s' % (BASE_URI, uri)
                else:
                    uri = '%s/%s' % (BASE_URI, uri)
            if uri.startswith(BASE_URI):
                return uri

    def tr(self, table, index=None):
        xs = table.findAll('tr', recursive=False)
        if index:
            return xs[index]
        return xs

    def td(self, tr, index=None):
        xs = tr.findAll('td', recursive=False)
        if index:
            return xs[index]
        return xs

    def strip(self, s):
        if s is None:
            return None
        try:
            s = s.replace('&nbsp;', ' ')
            s = s.strip('\t\r\n ')
            s1 = None
            while s1 != s:
                s1 = s
                s = re.sub('^\\\\(n|r|t)', '', s)
                s = re.sub('\\\\(n|r|t)$', '', s)
            return s
        except:
            return ''


class MP(Scraper):
    @property
    def start_url(self):
        return self.resolve('/parliamentarians')

    def links(self, url):
        html = self.get(url)
        xs = self.lx(html)
        next_page = self.l(html, '&gt;')
        return (xs, self.resolve(next_page),)
        
    def lx(self, html):
        td = html.find('td', attrs={'class': 'content_text_column'})
        xs = td.findAll('a', attrs={'class':'content_subheader'})
        return [x['href'] for x in xs]
    
    def details(self, url):
        html = self.get(url)
        tx = self.tr(html.find('td', attrs={'class': 'content_text_column'}).find('table'))

        constituency, region = self.scrape_constituency_and_region(tx[0])

        d =  dict(name=self.scrape_name(tx[0]),
                  constituency=constituency,
                  region=region)
        d.update(self.scrape_bio(tx[0]))

        return d

    def scrape_name(self, tr):
        # div.left_subheaders > strong:nth-child(1) 
        text = tr.find('div', attrs={'class': 'left_subheaders'}).text
        match = re.match('^(Hon.)?\s*([^\s].*)', text.strip(), flags=re.IGNORECASE)
        return match.group(2) if match else None

    def scrape_constituency_and_region(self, tr):
        # div.content_subheader
        text = tr.find('div', attrs={'class': 'content_subheader'}).text
        match = re.match('^(MP for)?\s*([^\s].+)\s+constituency,\s*(\w+)( Region)?', 
                        text.strip(), flags=re.IGNORECASE)
        return match.group(2), match.group(3) if match else None


    def scrape_bio(self, tr):
        # .content_text_column > div:nth-child(1) > table:nth-child(1) > tbody:nth-child(1) > tr:nth-child(1) > td:nth-child(2) > table:nth-child(4)
        return {}

if __name__ == "__main__":
    main()
