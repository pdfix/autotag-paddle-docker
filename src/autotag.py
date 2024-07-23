import tempfile
from paddleocr import PPStructure, save_structure_res
from pdfixsdk.Pdfix import *
from tqdm import tqdm
import cv2
import os
import sys
from paddle.utils import try_import
from PIL import Image


class PdfixException(Exception):
    def __init__(self, message: str = ""):
        self.errno = GetPdfix().GetErrorType()
        self.add_note(message if len(message) else str(GetPdfix().GetError()))


def autotag_page(
    page: PdfPage, pdfix: Pdfix, lang: str, doc_struct_elem: PdsStructElement
) -> bytes:
    """
    Renders a PDF page into a temporary file, which is then used for OCR.

    Parameters
    ----------
    page : PdfPage
        The PDF page to be processed for OCR.
    pdfix : Pdfix
        The Pdfix SDK object.
    lang : str
        The language identifier for OCR.

    Returns
    -------
    bytes
        Raw PDF bytes.
    """

    zoom = 2.0
    pageView = page.AcquirePageView(zoom, kRotate0)
    if pageView is None:
        raise PdfixException("Unable to acquire the page view")

    width = pageView.GetDeviceWidth()
    height = pageView.GetDeviceHeight()
    # Create an image
    image = pdfix.CreateImage(width, height, kImageDIBFormatArgb)
    if image is None:
        raise PdfixException("Unable to create the image")

    # Render page
    renderParams = PdfPageRenderParams()
    renderParams.image = image
    renderParams.matrix = pageView.GetDeviceMatrix()
    if not page.DrawContent(renderParams):
        raise PdfixException("Unable to draw the content")

    # Create temp file for rendering
    with tempfile.NamedTemporaryFile() as tmp:
        # Save image to file
        stm = pdfix.CreateFileStream(tmp.name + ".jpg", kPsTruncate)
        if stm is None:
            raise PdfixException("Unable to create the file stream")

        imgParams = PdfImageParams()
        imgParams.format = kImageFormatJpg
        imgParams.quality = 100
        if not image.SaveToStream(stm, imgParams):
            raise PdfixException("Unable to save the image to the stream")

        ocr_engine = PPStructure(show_log=True, lang='en')
        # ocr_engine = PPStructure(show_log=True, image_orientation=True)
        # ocr_engine = PPStructure(table=True, ocr=False, show_log=True, lang='en')
        """
        ocr_engine = PPStructure(
            show_log=True,
            lang="en",
            enable_mkldnn=True,  # results may be unstable
            layout_model_dir="models/layout/picodet_lcnet_x1_0_fgd_layout_infer/",
            table_model_dir="models/table/en_ppstructure_mobile_v2.0_SLANet_infer/",
            det_model_dir="models/det/en_PP-OCRv3_det_infer/",
            rec_model_dir="models/rec/en_PP-OCRv4_rec_infer/",
        )
        """
        
        #img = Image.open(tmp.name + ".jpg")
        img = cv2.imread(tmp.name + ".jpg")
        result = ocr_engine(img)
        #save_structure_res(
        #    result,
        #    os.path.dirname(tmp.name + ".jpg"),
        #    os.path.basename(tmp.name + ".jpg").split(".")[0],
        #)

        # Prepare page view for coordinate transformation
        page_width = page.GetCropBox()
        rotate = page.GetRotate()
        page_width = page_width.right - page_width.left
        if rotate == kRotate90 or rotate == kRotate270:
            page_width = page_width.top - page_width.bottom
        zoom = width / page_width
        page_view = page.AcquirePageView(zoom, 0)

        # Pre-create objects from Paddle engine to the pagemap
        page_map = page.AcquirePageMap()

        # Iterate blocks. It's only one level in this model
        # res_cp = deepcopy(result)
        # save res
        for region in result:
            # roi_img = region.pop("img")
            # f.write("{}\n".format(json.dumps(region)))

            # print (region["type"])
            # print (region["bbox"])

            # if (
            #    region["type"].lower() == "table"
            #    and len(region["res"]) > 0
            #    and "html" in region["res"]
            # ):
            #    to_excel(region["res"]["html"], excel_path)
            # elif region["type"].lower() == "figure":
            #    cv2.imwrite(img_path, roi_img)

            # Get image height
            # img_h = img.shape[0]
            # struct_elem['BBox'] = region["bbox"]
            # struct_elem['BBox'] = [b.block.x_1 * scale, (img_h - b.block.y_2) * scale,
            #                       b.block.x_2 * scale, (img_h - b.block.y_1) * scale]

            rect = PdfDevRect()
            rect.left = int(region["bbox"][0])
            rect.top = int(region["bbox"][1])
            rect.right = int(region["bbox"][2])
            rect.bottom = int(region["bbox"][3])
            bbox = page_view.RectToPage(rect)

            # Create initial element
            parent = PdeElement(None)
            pdeElemType = kPdeText  # text (default)
            if region["type"].lower() == "table":
                pdeElemType = kPdeTable
            elif region["type"].lower() == "figure":
                pdeElemType = kPdeImage

            elem = page_map.CreateElement(pdeElemType, parent)
            elem.SetBBox(bbox)
            if region["type"].lower() == "title":  # title
                elem.SetTextStyle(kTextH1)

        # Recognize page
        page_map.CreateElements()

        # Prepare the struct element for page
        page_elem = doc_struct_elem.AddNewChild(
            "NonStruct", doc_struct_elem.GetNumChildren()
        )
        page_map.AddTags(page_elem, False, PdfTagsParams())

        # Cleanup
        page_view.Release()
        page_map.Release()


def autotag(
    input_path: str,
    output_path: str,
    license_name: str,
    license_key: str,
    lang: str = "en",
) -> None:
    """
    Run layput recognition using Paddle.

    Parameters
    ----------
    input_path : str
        Input path to the PDF file.
    output_path : str
        Output path for saving the PDF file.
    license_name : str
        Pdfix SDK license name.
    license_key : str
        Pdfix SDK license key.
    lang : str, optional
        Language identifier for OCR Paddle. Default value "en".
    """

    pdfix = GetPdfix()
    if pdfix is None:
        raise Exception("Pdfix Initialization fail")

    if license_name and license_key:
        if not pdfix.GetAccountAuthorization().Authorize(license_name, license_key):
            raise Exception("Pdfix Authorization fail")
    else:
        print("No license name or key provided. Using Pdfix trial")

    # Open doc
    doc = pdfix.OpenDoc(input_path, "")
    if doc is None:
        raise Exception("Unable to open the PDF " + pdfix.GetError())

    # Remove old structure and prepare an empty structure tree
    doc.RemoveTags()
    struct_tree = doc.CreateStructTree()
    doc_struct_elem = struct_tree.GetStructElementFromObject(struct_tree.GetObject())

    doc_num_pages = doc.GetNumPages()

    # Process each page
    for i in tqdm(range(0, doc_num_pages), desc="Processing pages"):
        # Acquire page
        page = doc.AcquirePage(i)
        if page is None:
            raise PdfixException("Unable to acquire the page")

        try:
            autotag_page(page, pdfix, lang, doc_struct_elem)
        except Exception as e:
            raise e

        page.Release()

    if not doc.Save(output_path, kSaveFull):
        raise Exception("Unable to save PDF " + pdfix.GetError())
