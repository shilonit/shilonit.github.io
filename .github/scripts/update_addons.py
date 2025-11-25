import os
import hashlib
import zipfile
from lxml import etree
from copy import deepcopy

# Paths
ADDONS_XML = 'addons.xml'
ADDONS_MD5 = 'addons.xml.md5'
ZIPS_DIR = 'zips/'

# Compute MD5 checksum for a file
def compute_md5(file_path):
    hash_md5 = hashlib.md5()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

# Extract addon.xml from a zip file
def extract_addon_xml(zip_path):
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        for name in zip_ref.namelist():
            if name.endswith('addon.xml'):
                with zip_ref.open(name) as addon_file:
                    return addon_file.read()
    return None

# Merge metadata without overwriting en_GB with en
def merge_metadata(existing_ext, new_ext):
    special_tags = ['summary', 'description', 'disclaimer']
    for tag in special_tags:
        existing_tags = {el.get('lang'): el for el in existing_ext.findall(tag)}
        for new_el in new_ext.findall(tag):
            lang = new_el.get('lang')
            if lang == "en" and "en_GB" in existing_tags:
                continue
            if lang in existing_tags:
                existing_tags[lang].text = new_el.text
            else:
                existing_ext.append(new_el)

    for new_el in new_ext:
        if new_el.tag not in special_tags and new_el.tag != 'import':
            existing_el = existing_ext.find(new_el.tag)
            if existing_el is not None:
                existing_ext.remove(existing_el)
            existing_ext.append(new_el)

# Update local addon.xml file
def update_local_addon_xml(existing_path, addon_xml_data):
    new_tree = etree.fromstring(addon_xml_data)

    if os.path.exists(existing_path):
        try:
            tree = etree.parse(existing_path)
            root = tree.getroot()
            root.attrib.update(new_tree.attrib)
            existing_metadata = root.find("extension[@point='xbmc.addon.metadata']")
            new_metadata = new_tree.find("extension[@point='xbmc.addon.metadata']")
            if existing_metadata is not None and new_metadata is not None:
                merge_metadata(existing_metadata, new_metadata)

            tree.write(existing_path, pretty_print=True, xml_declaration=True, encoding='UTF-8')
            print(f"✅ Updated local addon.xml at {existing_path}")
        except Exception as e:
            print(f"❌ Failed to update local addon.xml at {existing_path}: {e}")
    else:
        with open(existing_path, 'wb') as f:
            f.write(addon_xml_data)
        print(f"📄 Saved new addon.xml at {existing_path}")

# Synchronize requires section (imports)
def sync_requires(addon, addon_tree):
    new_imports = [(imp.get('addon')) for imp in addon_tree.findall('requires/import')]
    existing_imports = [(imp.get('addon')) for imp in addon.findall('requires/import')]

    # Remove imports that no longer exist
    for imp in addon.findall('requires/import'):
        if imp.get('addon') not in new_imports:
            addon.find('requires').remove(imp)

    # Add new imports
    if addon_tree.find('requires') is not None:
        if addon.find('requires') is None:
            addon.insert(0, deepcopy(addon_tree.find('requires')))
        else:
            for new_imp in addon_tree.findall('requires/import'):
                if new_imp.get('addon') not in existing_imports:
                    addon.find('requires').append(deepcopy(new_imp))

# Synchronize extensions (except metadata)
def sync_extensions(addon, addon_tree):
    new_exts = [(ext.get('point'), ext.get('library')) for ext in addon_tree.findall('extension')]
    existing_exts = [(ext.get('point'), ext.get('library')) for ext in addon.findall('extension')]

    # Remove old extensions that no longer exist
    for old_ext in addon.findall('extension'):
        key = (old_ext.get('point'), old_ext.get('library'))
        if key not in new_exts and old_ext.get('point') != 'xbmc.addon.metadata':
            addon.remove(old_ext)

    # Add new extensions
    for new_ext in addon_tree.findall('extension'):
        key = (new_ext.get('point'), new_ext.get('library'))
        if key not in existing_exts and new_ext.get('point') != 'xbmc.addon.metadata':
            addon.append(deepcopy(new_ext))

# Update addons.xml with new addon.xml content
def update_addons_xml_from_addon(addon_xml_data):
    addon_tree = etree.fromstring(addon_xml_data)
    plugin_id = addon_tree.get('id')
    version = addon_tree.get('version')
    try:
        tree = etree.parse(ADDONS_XML)
        root = tree.getroot()
    except Exception as e:
        print(f"Error parsing {ADDONS_XML}: {e}")
        return

    for addon in root.findall('addon'):
        if addon.get('id') == plugin_id:
            print(f"\n📦 Updating {plugin_id} in {ADDONS_XML}")
            addon.attrib.update(addon_tree.attrib)

            # Synchronize requires
            sync_requires(addon, addon_tree)

            # Merge metadata
            existing_metadata = addon.find("extension[@point='xbmc.addon.metadata']")
            new_metadata = addon_tree.find("extension[@point='xbmc.addon.metadata']")
            if existing_metadata is not None and new_metadata is not None:
                merge_metadata(existing_metadata, new_metadata)
            elif new_metadata is not None and existing_metadata is None:
                addon.append(deepcopy(new_metadata))

            # Synchronize extensions
            sync_extensions(addon, addon_tree)

            tree.write(ADDONS_XML, pretty_print=True, xml_declaration=True, encoding='UTF-8')
            print(f"✅ Updated {plugin_id} to version {version}")
            return

    print(f"⚠️ {plugin_id} not found in {ADDONS_XML}, adding new addon...")
    root.append(addon_tree)
    tree.write(ADDONS_XML, pretty_print=True, xml_declaration=True, encoding='UTF-8')
    print(f"✅ Added {plugin_id} version {version}")

# Main logic
def main():
    for root_dir, _, files in os.walk(ZIPS_DIR):
        for file_name in files:
            if file_name.endswith('.zip'):
                zip_path = os.path.join(root_dir, file_name)
                addon_xml_data = extract_addon_xml(zip_path)
                if not addon_xml_data:
                    print(f"❌ addon.xml not found in {file_name}")
                    continue

                try:
                    addon_tree = etree.fromstring(addon_xml_data)
                    plugin_id = addon_tree.get('id')
                except Exception as e:
                    print(f"❌ Failed to parse addon.xml in {file_name}: {e}")
                    continue

                # Update local addon.xml
                existing_path = os.path.join(root_dir, 'addon.xml')
                update_local_addon_xml(existing_path, addon_xml_data)

                # Update main addons.xml
                update_addons_xml_from_addon(addon_xml_data)

    # Update MD5 checksum
    md5 = compute_md5(ADDONS_XML)
    with open(ADDONS_MD5, 'w') as f:
        f.write(md5)
    print(f"\n🔐 MD5 checksum updated in {ADDONS_MD5}")

if __name__ == "__main__":
    main()
