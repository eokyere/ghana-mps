#! /usr/bin/env python

import logging
import re
import yaml

import helper


BASE_URI = 'http://www.parliament.gh'

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


def main():
    mps = scrape_mps()
    log.debug(mps)
    
    fl = open('data/mps.yml', 'w')
    yaml.safe_dump(mps, fl)
    fl.close()

def scrape_mps():
    parser = MP(BASE_URI)
    next = parser.start_url    
    mps = []

    while next:
        log.info('>>> Retrieving links from: %s' % next)
        urls, next = parser.links(next)
        mps.extend([parser.data(url) for url in urls])
    return mps

def slugify(text):
    return '-'.join(re.compile(r'[\.,;]').sub('', text.lower()).split())


class MP(helper.Scraper):
    def data(self, url):
        """Scrape MPs bio, employment data, and memberships

        :returns: dict of MPs data
        """
        html = self.get(url)

        tr = self.tr(html.find('td', attrs={'class': 'content_text_column'}).find('table'))

        constituency, region = self.constituency_and_region(tr[0])
        title, full_name = self.full_name(tr[0])

        d = dict(title=title,
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

        d['phone'] = d['telephone']
        d.pop('telephone')

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


class Committee(helper.Scraper):
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
