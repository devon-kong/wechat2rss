class W2r < Formula
  include Language::Python::Virtualenv

  desc "CLI for managing a self-hosted Wechat2RSS service"
  homepage "https://github.com/YOUR_GITHUB_USERNAME/wechat2rss-cli"
  url "https://github.com/YOUR_GITHUB_USERNAME/wechat2rss-cli/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "REPLACE_WITH_RELEASE_TARBALL_SHA256"
  license "MIT"

  depends_on "python@3.12"

  def install
    virtualenv_install_with_resources
  end

  test do
    output = shell_output("#{bin}/w2r --help")
    assert_match "CLI for self-hosted Wechat2RSS", output
  end
end
