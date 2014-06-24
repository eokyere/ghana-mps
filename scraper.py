#! /usr/bin/env python

from bs4 import BeautifulSoup

import helper
import logging
import re
import requests
import yaml


BASE_URI = 'http://www.parliament.gh'

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


def main():
    scrape_mps()


def scrape_mps():
    parser = MP()
    next = parser.start_url    
    mps = []

    while next:
        log.info('>>> Retrieving links from: %s' % next)
        urls, next = parser.links(next)
        mps.extend([parser.data(url) for url in urls])
        next = None

    log.debug(mps)

    fl = open('mps.yml', 'w')
    yaml.safe_dump(mps, fl)
    fl.close()


def slugify(text):
    return '-'.join(text.lower().replace('.', '').split())


class Scraper(object):
    def tr(self, table, index=None):
        """Scrape table rows 

        This method finds tr non-recursively 
        (BeautifulSoup.findAll is recursive by default)

        :param index: index of tr node to be returned
        :returns: table rows (tr) of the supplied table.
        """
        xs = table.findAll('tr', recursive=False)
        if index:
            return xs[index]
        return xs

    def td(self, tr, index=None):
        """Scrape table data. 

        This method finds td non-recursively 
        (BeautifulSoup.findAll is recursive by default)

        :param index: index of td node to be returned
        :returns: list of td, or td node if index supplied
        """
        xs = tr.findAll('td', recursive=False)
        if index:
            return xs[index]
        return xs

    def href(self, s, text):
        """Scrape the href of an anchor tag.

        :param text: anchor text
        :returns: href string
        """
        try:
            return s.find('a', text=text).parent['href']
        except:
            return None


    def get(self, url):
        """Returns BeautifulSoup of the content at the supplied url 
        (resolved to the BASE_URI)
        """
        url = self.resolve(url)    
        return self.bs(requests.get(url, headers=helper.headers).content)
    
    def bs(self, content):
        """Returns BeautifulSoup of the supplied content (html)
        """
        return BeautifulSoup(self.strip(content))
    
    def resolve(self, uri):
        """Resolves the supplied uri relative to the BASE_URI
        """
        if uri is not None:
            if not uri.startswith('http://'):
                if uri.startswith('/'):
                    uri = '%s%s' % (BASE_URI, uri)
                else:
                    uri = '%s/%s' % (BASE_URI, uri)
            if uri.startswith(BASE_URI):
                return uri

    def strip(self, s):
        """Clean up http 'space' entities
        """
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
    def data(self, url):
        """Scrape MPs bio, employment data, and memberships

        :returns: dict of MPs data
        """
        html = self.get(url)

        tr = self.tr(html.find('td', attrs={'class': 'content_text_column'}).find('table'))

        constituency, region = self.constituency_and_region(tr[0])
        title, full_name = self.full_name(tr[0])

        d =  dict(title=title,
                  full_name=full_name,
                  constituency=constituency,
                  region=region)

        d.update(self.bio_and_memberships(tr[0]))
        d.update(self.emp_others(tr[-1]))
        d.update(tag=url.split('/')[-1])
        d.update(_slug=slugify(full_name))

        key = 'party'
        d[key] = d[key].split('(')[0].strip()

        for key in ('employment', 'education', 'committees'):
            d[key] = d[key].split('\n')

        return d

    def full_name(self, tr):
        """Title and Full name 
        
        :param tr: the table row that contains the MPs name
        :returns: tuple(string, string) of the title and full name of an MP
        """
        # div.left_subheaders > strong:nth-child(1) 
        text = tr.find('div', attrs={'class': 'left_subheaders'}).text
        match = re.match('^(Hon.)?\s*([^\s][^\(]*)\s*(\([^\)]+\))?', text.strip(), flags=re.IGNORECASE)
        title, name = (match.group(3), match.group(2)) if match else (None, None)
        if title:
            title = title[1:-1]
        return title, name


    def constituency_and_region(self, tr):
        """Constituency and region names.

        :returns: tuple(string, string) of constituency and region names
        """
        # div.content_subheader
        text = tr.find('div', attrs={'class': 'content_subheader'}).text
        match = re.match('^(MP for)?\s*([^\s].+)\s+constituency,\s*(\w+)( Region)?', 
                        text.strip(), flags=re.IGNORECASE)
        return match.group(2), match.group(3) if match else None

    def bio_and_memberships(self, tr):
        """
        Keys are: committees, hometown, marital_status, profession, telephone, 
        religion, date_of_birth, party, education, email

        :returns: bio and memberships dict of from MP detailed page
        """
        def f(node):
            xs = node.findAll('span', attrs={'class': 'content_txt'})
            return (self.key(xs[0].text), self.cleaned_text(xs[1].text))
        return dict(f(x) for x in tr.findAll('td', attrs={'class': 'line_under_table'}))

    def emp_others(self, tr):
        """Returns the employment and 'others' info from an MP detailed page
        """
        def f(node):
            xs = node.findAll('td')
            return (self.key(xs[0].text), self.cleaned_text(xs[1].text))
        return dict(f(x) for x in tr.findAll(attrs={'class': 'content_txt'}))

    @property
    def start_url(self):
        return self.resolve('/parliamentarians')

    def links(self, url):
        """Extracts the links for detailed pages of MPs 
        and the link to the next page for detailed pages links (if any)
        """
        html = self.get(url)
        next_page = self.href(html, '&gt;')
        return (self.lx(html), self.resolve(next_page),)
        
    def lx(self, html):
        """Returns the links for the detailed pages of MPs on the MPs overview page
        """
        td = html.find('td', attrs={'class': 'content_text_column'})
        xs = td.findAll('a', attrs={'class':'content_subheader'})
        return [x['href'] for x in xs]
    
    def key(self, text):
        return str(text.lower().strip().replace(':', '').replace(' ', '_'))

    def cleaned_text(self, text):
        text = text.strip().replace('\r', '').replace('\n\n', '\n')
        while text.endswith('\n'):
            text = text[:-2]
        while text.startswith('\n'):
            text = text[2:]
        return text


class Committee(Scraper):
    @property
    def start_url(self):
        return self.resolve('/committees')

    def links(self, url):
        """Extract the name and link for committee
        """
        html = self.get(url)
        committees = html.findAll('a', attrs={'class':'committee_repeater'})
        return [(self.strip(x.string), x['href']) for x in committees]

  
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='[gh-mps scraper | %(levelname)s] %(message)s')
    main()
