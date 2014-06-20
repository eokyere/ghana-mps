#! /usr/bin/env python

from bs4 import BeautifulSoup

import re
import requests
import helper


BASE_URI = 'http://www.parliament.gh'


def main(args=None):
    api = MP()
    links, next = api.links(api.start_url)

    print api.data(links[0])
    print api.popit(links[0])


def slugify(text):
    return '-'.join(text.strip().lower().split(' '))

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
    def popit(self, url):
        data = self.data(url)

        names = data['full_name'].split(' ')

        return {

            "family_name": names[-1],
            "given_names": ' '.join(names[:-1]),
            # "honorific_prefix": "Mr",
            # "id": "org.odekro/person/451",
            # "identifiers": [
            #     {
            #         "identifier": "5551",
            #         "scheme": "myreps_person_id"
            #     }
            # ],
            # "memberships": [
            #     {
            #         "id": "org.mysociety.za/membership/451",
            #         "organization_id": "org.mysociety.za/party/da",
            #         "person_id": "org.mysociety.za/person/451"
            #     },
            #     {
            #         "area": {
            #             "id": "org.mysociety.za/mapit/code/p/KZN",
            #             "name": "KwaZulu-Natal"
            #         },
            #         "en_ddate": "2011-09-24",
            #         "end_reason": "Resigned",
            #         "id": "org.mysociety.za/membership/680",
            #         "label": "Member for %s",
            #         "organization_id": "org.mysociety.za/house/national-assembly",
            #         "person_id": "org.mysociety.za/person/451",
            #         "role": "Member",
            #         "start_date": "2009-05-06"
            #     }
            # ],
            "name": data['full_name'],
            "slug": slugify(data['full_name'])        
        }

    def data(self, url):
        """Scrape MPs bio and employment data

        :returns: dict of MPs data
        """
        html = self.get(url)
        tr = self.tr(html.find('td', attrs={'class': 'content_text_column'}).find('table'))

        constituency, region = self.constituency_and_region(tr[0])

        d =  dict(full_name=self.full_name(tr[0]),
                  constituency=constituency,
                  region=region)
        d.update(self.bio(tr[0]))
        d.update(self.emp_others(tr[-1]))

        key = 'party'
        d[key] = d[key].split('(')[0].strip()

        for key in ('employment', 'education'):
            d[key] = d[key].split('\n')

        return d

    def full_name(self, tr):
        """Scrape 
        :param tr: the table row that contains the MPs name
        :returns: the full name string of an MP
        """
        # div.left_subheaders > strong:nth-child(1) 
        text = tr.find('div', attrs={'class': 'left_subheaders'}).text
        match = re.match('^(Hon.)?\s*([^\s].*)', text.strip(), flags=re.IGNORECASE)
        return match.group(2) if match else None

    def constituency_and_region(self, tr):
        """Constituency and region names.

        :returns: the tuple(string, string) of constituency and region names
        """
        # div.content_subheader
        text = tr.find('div', attrs={'class': 'content_subheader'}).text
        match = re.match('^(MP for)?\s*([^\s].+)\s+constituency,\s*(\w+)( Region)?', 
                        text.strip(), flags=re.IGNORECASE)
        return match.group(2), match.group(3) if match else None

    def bio(self, tr):
        """
        :returns: the scraped bio from an MP detailed page
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
        return text.lower().strip().replace(':', '').replace(' ', '_')

    def cleaned_text(self, text):
        text = text.strip().replace('\r', '').replace('\n\n', '\n')
        while text.endswith('\n'):
            text = text[:-2]
        while text.startswith('\n'):
            text = text[2:]
        return text


if __name__ == "__main__":
    main()
