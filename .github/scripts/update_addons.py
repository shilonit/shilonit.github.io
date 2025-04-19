import os, re, hashlib
from lxml import etree

## Paths
addons_xml_path = 'addons.xml'
addons_xml_md5_path = 'addons.xml.md5'
zips_path = 'zips/'

## Helper function to compute md5 checksum
def compute_md5(file_path):
    with open(file_path, 'rb') as f:
        file_hash = hashlib.md5()
        while chunk := f.read(8192):
            file_hash.update(chunk)
    return file_hash.hexdigest()

## Load and update addons.xml
def update_addons_xml(zip_file, version):
    match_plugin = re.match(r'plugin\.video\.(\w+)-(\d+(\.\d+){0,2})\.zip', zip_file)

    if match_plugin:
        plugin_id = f'plugin.video.{match_plugin.group(1)}'
    else:
        print(f"File name {zip_file} does not match expected format.")
        return

    ## Parse XML
    tree = etree.parse(addons_xml_path)
    root = tree.getroot()

    ## Find and update the relevant addon entry
    updated = False
    for addon in root.findall('addon'):
        if addon.get('id') == plugin_id:
            old_version = addon.get('version')
            print(f"Old version for {plugin_id}: {old_version}")
            addon.set('version', version)
            updated = True
            print(f"Updated {plugin_id} to version {version}")

    if updated:
        tree.write(addons_xml_path, pretty_print=True, xml_declaration=True, encoding='UTF-8')
        print("addons.xml updated.")

def main():
    for root, dirs, files in os.walk(zips_path):
        for file_name in files:
            if file_name.endswith('.zip'):
                match_plugin = re.match(r'plugin\.video\.(\w+)-(\d+(\.\d+){0,2})\.zip', file_name)

                if match_plugin:
                    version = match_plugin.group(2)
                    update_addons_xml(file_name, version)

    ## Update MD5 checksum
    new_md5 = compute_md5(addons_xml_path)
    with open(addons_xml_md5_path, 'w') as f:
        f.write(new_md5)
    print(f"Updated {addons_xml_md5_path} with new checksum.")

if __name__ == "__main__":
    main()
