#
# Noesis : SH4 PC/Win bin map file viewer plugin
# 
#  Authors:
#
# Original Noesis map loader script from:
# Laurynas Zubavičius (Sparagas)
# Rodolfo Nuñez (roocker666)
# https://github.com/Sparagas/Silent-Hill
#
# Alanm1: Texture loader 
#     Requires the global ??gb.bin from the same area of map to get the global texture. 
#
# Search idea:
# Durik256 - https://forum.xentax.com/viewtopic.php?t=26090
#
# HunterStanton: SH4 bin file and texture format research 
# https://github.com/HunterStanton/sh4bin
# https://github.com/HunterStanton/sh4texturetool
#
# Known issue: 
#    Does not support some SH4 PC map bin files.
#    Some mesh faces show up flipped. turn off Noesis backface culling to see all faces
#           

from inc_noesis import *


def registerNoesisTypes():
    handle = noesis.register("Silent Hill 4: THe Room (Win) map", ".bin")
    noesis.setHandlerTypeCheck(handle, CheckType)
    noesis.setHandlerLoadModel(handle, LoadModel)
    #noesis.logPopup()
    return 1


def CheckType(data):
    if len(data) < 4:
        return 0
    bs = NoeBitStream(data)
    num_block = bs.readUInt()
    if len(data) < 4 + 4 * num_block:
        return 0
    block = [0] * num_block
    for i in range(num_block):
        block[i] = bs.readUInt()
        if len(data) < block[i]:
            return 0
    for i in range(num_block):
        bs.seek(block[i])
        magic = bs.read("2H")
        if magic[0] == 0x0001 and magic[1]==0xFC03:
            return 1
    return 0

def LoadTexture(data, texList, tex_chunkList, tex_no = 0):
    bs = NoeBitStream(data)
    n_chunk = bs.readUInt()
    offs = struct.unpack("I"*n_chunk, bs.read(n_chunk*4))
    cur_mesh = 0 # assuming mesh and texture are one to one match inside bin file order
    for i in range(n_chunk):   # looking for texture chunk
        bs.seek(offs[i])
        magic=bs.readUShort()
        magic2=bs.readUShort()
        
        if magic == magic2: 
            chunk_id = i
            if tex_chunkList != None:    # need to check if texture is from a supported mesh type
                if cur_mesh < len (tex_chunkList) and tex_chunkList[cur_mesh] >= 0:  # this texture is paired to a supported mesh
                    tex_chunkList[cur_mesh] = chunk_id  # save the chunk number of texture for look up
                    cur_mesh += 1 
                else:                                
                    cur_mesh += 1
                    continue
            else:
                chunk_id = 255  # speial chunk id for global textures
            bs.seek(0xc,NOESEEK_REL)
            total_tex = magic + magic2
            n_tex_grp = magic
            bs.seek(total_tex * 0x4 + n_tex_grp*0x10,NOESEEK_REL)
            image_cnt=[]
            tex_offs=[]
            
            offs_base = bs.tell()
            for t in range(n_tex_grp): # texture header offsets
                entry_start = bs.tell()
                bs.readUInt()
                image_cnt.append(bs.readUInt())
                bs.readUInt()
                tex_offs.append((bs.readUInt() + entry_start))
            print ("image cnt",image_cnt)
            for t in range(n_tex_grp):

                bs.seek(tex_offs[t])  # jump to texture header
                for s in range(image_cnt[t]):  # Texture can have more than one image
                    tex_start = bs.tell()
                    bs.seek(0x20,NOESEEK_REL)
                    ddsWidth = bs.readUInt()
                    ddsHeight = bs.readUInt()
                    formatBytes = bs.read(4)
                    if formatBytes[2] != 0:
                        format = formatBytes.decode('utf-8')
                    else:
                        format = hex(formatBytes[0]) # not a DXT string
                    mip_cnt = bs.readUInt()
                    ddsSize = bs.readUInt()

                    bs.seek(0x1c,NOESEEK_REL)
                    imgDataOffs = struct.unpack("I"*7, bs.read(4*7))
                    unknown = bs.readUInt()
                    pos = bs.tell()
                    bs.seek(imgDataOffs[0] + tex_start)  # only load first mipmap, highest resolution

                    texName = "Tex_" + str(chunk_id) + '_' + str(t) + "_"  + str(s)  # image_chunk_grpindex_subindex
                    print(texName,ddsWidth,ddsHeight,format,mip_cnt,hex(ddsSize))                                        
                    ddsData = bs.readBytes(ddsSize)                  
                    dxt = noesis.NOESISTEX_RGBA32   # if it is not DXT , last guess would be a raw uncompress image
                    if format == 'DXT1':
                        dxt =  noesis.NOESISTEX_DXT1
                    elif format == 'DXT3':
                        dxt =  noesis.NOESISTEX_DXT3
                    elif format == 'DXT5':
                        dxt =  noesis.NOESISTEX_DXT5
                    else:                        
                        print ("unknown DXT format!!!")    

                    texList.append(NoeTexture(texName, ddsWidth, ddsHeight, ddsData, dxt))
                    bs.seek(pos) 
                tex_no += 1               
    return 1

def mark_valid_texture(data, tex_chunkList): 
    bs = NoeBitStream(data)
    n_chunk = bs.readUInt()
    offs = struct.unpack("I"*n_chunk, bs.read(n_chunk*4))
    found_mesh = False
    for i in range(n_chunk):   # looking for texture chunk
        bs.seek(offs[i])
        chunk_start = bs.tell()
        magic=bs.readUShort()
        magic2=bs.readUShort()
        bs.seek(chunk_start)
        if magic ==  magic2:  # texture chunk  , num tex == num palette
            pass
        elif (magic == 0x0001 and magic2==0xFC03):  # world mesh,   (magic == 0x7000 and magic2 == 0x0FC0) or            
                tex_chunkList.append(0)  #  texture to be loaded
                found_mesh = True
        elif magic == 0x0003:
                tex_chunkList.append(-1)  # texture to be ignored
    return found_mesh

def LoadModel(data, mdlList):
    texList=[]
    matList=[]
    global bones
    bones = []
    tex_chunkList = []
    # mark texture of supported mesh
    if mark_valid_texture(data, tex_chunkList):
        need_gb_tex = True
    else:   
        need_gb_tex = False

    # load texture of supported mesh type
    LoadTexture(data,texList, tex_chunkList)
    print ("tex_chunkList",tex_chunkList)

    gb_start = len(texList)
    
    # get global texture
    if need_gb_tex:
        filepath = rapi.getInputName()
        basename  = os.path.splitext(os.path.basename(filepath))[0]
        dir = os.path.dirname(filepath)
        area_name = basename[:2]  # look for file names with the same first 2 characters
        gb_tex_fn = os.path.join(dir, area_name +"gb.bin")    
        if os.path.exists(gb_tex_fn): 
            with open(gb_tex_fn,"rb") as file:   
                LoadTexture(file.read(), texList, None, gb_start)
    
    # prcoess all mesh chunk
    bs = NoeBitStream(data)

    n_chunk = bs.readUInt()
    offs = struct.unpack("I"*n_chunk, bs.read(n_chunk*4))

    ctx = rapi.rpgCreateContext()
    cur_mesh = 0
    for i in range(n_chunk):   # looking for texture chunk
        bs.seek(offs[i])
        chunk_start = bs.tell()
        magic=bs.readUShort()
        magic2=bs.readUShort()
        bs.seek(chunk_start)
        if magic ==  magic2:  # texture chunk  , num tex == num palette
            pass
        elif (magic == 0x0001 and magic2==0xFC03):  # world mesh,   (magic == 0x7000 and magic2 == 0x0FC0) or            
            LoadMesh(bs,texList, matList, gb_start, tex_chunkList[cur_mesh])
            cur_mesh += 1
        elif magic == 0x0003: # and magic2 == 0xffff:
            cur_mesh += 1
            #readMesh(bs)
            
    try:
        mdl = rapi.rpgConstructModel()
    except:
        mdl = NoeModel()

    mdl.setModelMaterials(NoeModelMaterials(texList, matList))    
    mdlList.append(mdl)   
    return 1

def LoadMesh(bs,texList,matList, gb_start, tex_chunk_id):
    
    found_mesh = False
    chunk_start = bs.tell()
    bs.readUInt()  # magic,magic2
    mesh_cnt = bs.readUInt()
    mesh_offs = struct.unpack("I"*mesh_cnt, bs.read(4* mesh_cnt))
    mat_next_id = len(matList)

    for i in range(mesh_cnt):
        if mesh_offs[i] != 0:
            found_mesh = True
            bs.seek(chunk_start + mesh_offs[i])
            mesh_start = bs.tell()
            submesh_cnt = bs.readUInt()
            sm_offs = struct.unpack("I"*submesh_cnt, bs.read(4*submesh_cnt))
            for m in range(submesh_cnt):
                bs.seek(mesh_start + sm_offs[m])
                mesh_size  = bs.readUInt()
                bs.seek(8 , NOESEEK_REL)
                mat1 = struct.unpack("HH",bs.read(4))
                texinfo = struct.unpack("HH",bs.read(4))
                tex_id = mat1[0] - 1
                if mat1[1] != 0:   # using global texture
                    tex_chunk = 255   # special chunk id for global texture
                else:
                    tex_chunk = tex_chunk_id  
                subIdx = texinfo[1]
                texName = "Tex_" + str(tex_chunk) + '_' + str(tex_id) + "_" +str(subIdx)
                matName = "Mat_" + str(mat_next_id)
                mat_next_id += 1                
                mat=NoeMaterial(matName,texName)
                mat.setBlendMode(1,6)
                matList.append(mat) # create unique material for each mesh
                rapi.rpgSetMaterial(matName)

                bs.seek(0x0C,NOESEEK_REL)
                bmin = bs.read("4f")
                bmax = bs.read("4f")
                bs.seek(0x60,NOESEEK_REL)
                fnum = bs.readUInt()
                vnum = bs.readUInt()
                bs.seek(64, 1)
                unk1 = bs.readUInt()
                unk2 = bs.readUInt()

                bs.seek(16,NOESEEK_REL)
                fbuf = bs.read(fnum * 2)
                vbuf = bs.read(vnum * 24)
 
                rapi.rpgBindPositionBuffer(vbuf, noesis.RPGEODATA_FLOAT, 24)

                vbuf_format = 'fffBBBBff'
                vbuf_size = struct.calcsize(vbuf_format)
                r_offset = struct.calcsize('fff')
                b_offset = r_offset + struct.calcsize('BB')
                vbuf_array = bytearray(vbuf)
                for j in range(0, len(vbuf_array), vbuf_size):
                    vbuf_array[j + r_offset], vbuf_array[j + b_offset] = vbuf_array[j + b_offset], vbuf_array[j + r_offset]
                vbuf = bytes(vbuf_array)

                # flip mesh along y-axis (vertial direction)
                rapi.rpgSetTransform(NoeMat43((NoeVec3((-1, 0, 0)), NoeVec3((0, -1, 0)), NoeVec3((0, 0, 1)), NoeVec3((0, 0, 0)))))   
                rapi.rpgBindColorBufferOfs(vbuf, noesis.RPGEODATA_UBYTE, 24, 12, 4)
                rapi.rpgBindUV1BufferOfs(vbuf, noesis.RPGEODATA_FLOAT, 24, 16)


                offs_str = '{0:#010x}'.format(chunk_start)
                mesh_name = "mesh_" + offs_str + '_' + str(i) + '_' + str(m)         
                print (mesh_name,", mat id", texName, hex(mat1[0]),hex(mat1[1]), hex(texinfo[0]), hex(texinfo[1]), unk1, unk2, fnum)   
                #print (bmin,pmin,bmax,pmax)
                rapi.rpgSetName(mesh_name)        
                rapi.rpgCommitTriangles(fbuf, noesis.RPGEODATA_USHORT, fnum, noesis.RPGEO_TRIANGLE_STRIP)
         
                rapi.rpgClearBufferBinds() 
    return found_mesh
