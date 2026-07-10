class AiusageTracker < Formula
  include Language::Python::Virtualenv

  desc "Cross-platform menu bar usage tracker for Claude Code, Codex and other AI coding subscriptions"
  homepage "https://github.com/ahsanhabibakik/aiusage"
  url "https://github.com/ahsanhabibakik/aiusage/releases/download/v0.2.0/aiusage_tracker-0.2.0.tar.gz"
  sha256 "5dbf06410667c808832ec3178a471749373d0806b3a44e27d10eccd1fa46a1ab"
  license "MIT"

  depends_on "python@3.12"

  resource "six" do
    url "https://files.pythonhosted.org/packages/94/e7/b2c673351809dca68a0e064b6af791aa332cf192da575fd474ed7d6f16a2/six-1.17.0.tar.gz"
    sha256 "ff70335d468e7eb6ec65b95b99d3a2836546063f63acc5171de367e834932a81"
  end

  resource "Pillow" do
    url "https://files.pythonhosted.org/packages/1c/3d/bb7fca845737cf9d7dbde16ed1843984665ff2e0a518f5db43e77ec540b9/pillow-12.3.0.tar.gz"
    sha256 "3b8182a766685eaa002637e28b4ec8d6b18819a0c71f579bf0dbaa5830297cce"
  end

  resource "pystray" do
    url "https://files.pythonhosted.org/packages/5c/64/927a4b9024196a4799eba0180e0ca31568426f258a4a5c90f87a97f51d28/pystray-0.19.5-py2.py3-none-any.whl"
    sha256 "a0c2229d02cf87207297c22d86ffc57c86c227517b038c0d3c59df79295ac617"
  end

  # pystray's Linux tray backend (Ayatana/AppIndicator or Xlib fallback).
  # macOS uses pyobjc instead -- not vendored here (deep pyobjc dependency
  # chain); on macOS `aiusage tray` needs a manual
  # `pip install pyobjc-framework-Cocoa pyobjc-framework-Quartz` into the
  # keg's venv. `aiusage status` / `aiusage serve` work everywhere out of
  # the box with no extra step -- they don't touch pystray/PIL at all.
  on_linux do
    resource "python-xlib" do
      url "https://files.pythonhosted.org/packages/86/f5/8c0653e5bb54e0cbdfe27bf32d41f27bc4e12faa8742778c17f2a71be2c0/python-xlib-0.33.tar.gz"
      sha256 "55af7906a2c75ce6cb280a584776080602444f75815a7aff4d287bb2d7018b32"
    end
  end

  def install
    virtualenv_install_with_resources
  end

  def caveats
    on_linux do
      <<~EOS
        The tray icon (`aiusage tray`) needs a StatusNotifierItem/AppIndicator
        provider to actually show up in modern desktop panels (Plasma 6, GNOME
        with the AppIndicator extension). If your panel doesn't render it,
        use `aiusage serve` and open http://127.0.0.1:8737 instead.
      EOS
    end
  end

  test do
    system bin/"aiusage", "--help"
  end
end
