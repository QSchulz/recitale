import logging
import sys
import base64
import shlex
import subprocess
from email.utils import formatdate
from datetime import datetime
from builtins import str

from path import Path
import ruamel.yaml as yaml


logger = logging.getLogger("recitale." + __name__)


def remove_superficial_options(options):
    cleaned_options = options.copy()
    if "name" in cleaned_options:
        del cleaned_options["name"]
    if "exif" in cleaned_options:
        del cleaned_options["exif"]
    if "text" in cleaned_options:
        del cleaned_options["text"]
    if "type" in cleaned_options:
        del cleaned_options["type"]
    if "size" in cleaned_options:
        del cleaned_options["size"]
    if "float" in cleaned_options:
        del cleaned_options["float"]
    # "resize" only applies to image.copy() in templates, no need to propagate it to the cache since
    # the actual size of the "copy" thumbnail is part of the filename and will trigger a
    # regeneration if changed (thus "resize" setting is appropriately watched without regenerating
    # non-copy thumbnails).
    if "resize" in cleaned_options:
        del cleaned_options["resize"]
    return cleaned_options


class CustomFormatter(logging.Formatter):
    """Logging Formatter to add colors"""

    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    fmt_nok = "%(asctime)s %(levelname)s (%(filename)s:%(lineno)d) - %(message)s"
    fmt_ok = "%(asctime)s %(levelname)s - %(message)s"

    FORMATS = {
        logging.INFO: OKGREEN + fmt_ok + ENDC,
        logging.WARNING: WARNING + fmt_nok + ENDC,
        logging.ERROR: FAIL + fmt_nok + ENDC,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


def makeform(template, settings, gallery_settings):
    from_template = template.get_template("form.html")
    form = base64.b64encode(
        from_template.render(settings=settings, gallery=gallery_settings).encode(
            "Utf-8"
        )
    )
    return str(form, "utf-8")


def encrypt(password, template, gallery_path, settings, gallery_settings):
    encrypted_template = template.get_template("encrypted.html")
    index_plain = Path("build").joinpath(gallery_path, "index.html")
    cmd = "openssl enc -e -base64 -A -aes-256-cbc -md md5 -pass pass:%s" % shlex.quote(
        password
    )
    with open(index_plain, "r") as f:
        encrypted = subprocess.check_output(
            shlex.split(cmd), stdin=f, stderr=subprocess.DEVNULL
        )
    html = encrypted_template.render(
        settings=settings,
        form=makeform(template, settings, gallery_settings),
        ciphertext=str(encrypted, "utf-8"),
        gallery=gallery_settings,
    ).encode("Utf-8")
    return html


def rfc822(date):
    epoch = datetime.utcfromtimestamp(0).date()
    return formatdate((date - epoch).total_seconds())


def load_settings(folder):
    try:
        with open(
            Path(".").joinpath(folder, "settings.yaml").abspath(), "r"
        ) as settings:
            gallery_settings = yaml.safe_load(settings.read())
    except (yaml.error.MarkedYAMLError, yaml.YAMLError) as exc:
        msg = "There is something wrong in %s/settings.yaml" % folder
        if isinstance(exc, yaml.error.MarkedYAMLError):
            msg = msg + str(exc.context_mark)
        logger.error(msg)
        sys.exit(1)
    except ValueError:
        logger.error(
            "Incorrect data format, should be YYYY-MM-DD in %s/settings.yaml", folder
        )
        sys.exit(1)
    except Exception as exc:
        logger.exception(exc)
        sys.exit(1)

    if gallery_settings is None:
        logger.error("The %s/settings.yaml file is empty", folder)
        sys.exit(1)
    elif not isinstance(gallery_settings, dict):
        logger.error("%s/settings.yaml should be a dict", folder)
        sys.exit(1)
    elif "title" not in gallery_settings:
        logger.error("You should specify a title in %s/settings.yaml", folder)
        sys.exit(1)

    if gallery_settings.get("date"):
        try:
            datetime.strptime(str(gallery_settings.get("date")), "%Y-%m-%d")
        except ValueError:
            logger.error(
                "Incorrect data format, should be YYYY-MM-DD in %s/settings.yaml",
                folder,
            )
            sys.exit(1)
    return gallery_settings
